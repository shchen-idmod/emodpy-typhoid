#!/usr/bin/env python

import pandas as pd
import math
import pathlib # for a join
from functools import partial

# idmtools ...
from idmtools.assets import Asset, AssetCollection  #
from idmtools.builders import SimulationBuilder
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment
from idmtools_platform_comps.utils.python_requirements_ac.requirements_to_asset_collection import RequirementsToAssetCollection
from idmtools_models.templated_script_task import get_script_wrapper_unix_task

# emodpy
from emodpy.emod_task import EMODTask
import emodpy.emod_task 
#emodpy.emod_task.dev_mode = True

import manifest

base_year=1917
sim_years=122 # 100 OK
initial_pop=9712

def update_sim_bic(simulation, value):
    simulation.task.config.parameters.Base_Infectivity_Constant = value*0.1
    return {"Base_Infectivity": value}

def update_sim_random_seed(simulation, value):
    simulation.task.config.parameters.Run_Number = value
    return {"Run_Number": value}

def set_param_fn( config ):
    # sim nature, size and scope
    config.parameters.Simulation_Type = "TYPHOID_SIM"
    #config.parameters.Simulation_Type = "GENERIC_SIM" # for demographics
    #config.parameters.Enable_Environmental_Route = 1 # This should be implicit with TYPHOID_SIM; Fix in C++/G-O
    config.parameters.Simulation_Duration = sim_years*365.0
    #config.parameters.Enable_Skipping = 1  
    #config.parameters.Base_Individual_Sample_Rate = 0.25
    config.parameters.Base_Individual_Sample_Rate = 0.1

    # demographics
    #config.parameters.x_Birth = 3
    #config.parameters.x_Other_Mortality = 100 # just to add some additional fertility

    #config.parameters.Enable_Birth = 0 # temporary
    #config.parameters.Minimum_End_Time = 90 
    # cover up for default bugs in schema

    #Comment some things out while doing GENERIC_SIM testing
    def typhoid_report():
        config.parameters.Base_Year = base_year # to 1960
        config.parameters.Inset_Chart_Reporting_Start_Year = base_year
        config.parameters.Inset_Chart_Reporting_Stop_Year = 2040
        config.parameters.Report_Typhoid_ByAgeAndGender_Start_Year = 2021
        config.parameters.Report_Typhoid_ByAgeAndGender_Stop_Year = 2022
    typhoid_report()
    def generic_infect(): # for demographics
        config.parameters.Infectious_Period_Exponential = 10
        config.parameters.Incubation_Period_Constant = 10
        config.parameters.Base_Infectivity_Constant = 1
    #generic_infect()


    # reporting
    config.parameters.Enable_Demographics_Reporting = 0 
    #config.parameters.Enable_Property_Output = 1 
    #config.parameters["logLevel_default"] = "INFO"

    # typhoid
    config.parameters.Node_Contagion_Decay_Rate = 0.056278
    #config.parameters.Environmental_Incubation_Period = 1
    config.parameters.Typhoid_3year_Susceptible_Fraction = 0
    config.parameters.Typhoid_6month_Susceptible_Fraction = 0
    config.parameters.Typhoid_6year_Susceptible_Fraction = 0
    config.parameters.Typhoid_Acute_Infectiousness = 13435
    config.parameters.Typhoid_Carrier_Probability = 0.108
    #config.parameters.Typhoid_Carrier_Removal_Year = 2500 # not in this schema
    config.parameters.Typhoid_Chronic_Relative_Infectiousness = 0.241
    config.parameters.Typhoid_Contact_Exposure_Rate = 0.05717751694664575
    config.parameters.Typhoid_Environmental_Exposure_Rate = 0.04742897659197619
    def seasonal_forcing_to():
        config.parameters.Environmental_Cutoff_Days = 190.0 # not in this schema
        config.parameters.Environmental_Peak_Start = 40.0
        config.parameters.Environmental_Ramp_Down_Duration = 100.0
        config.parameters.Environmental_Ramp_Up_Duration = 28.0
    #seasonal_forcing_to()
    config.parameters.Typhoid_Exposure_Lambda = 5.19468669532742
    config.parameters.Typhoid_Prepatent_Relative_Infectiousness = 0.5
    config.parameters.Typhoid_Protection_Per_Infection = 0.98
    config.parameters.Typhoid_Subclinical_Relative_Infectiousness = 1
    config.parameters.Typhoid_Symptomatic_Fraction = 0.049739494850446146

    # overhead
    config.parameters.pop( "Serialized_Population_Filenames" )
    config.parameters.pop( "Serialization_Time_Steps" )

    return config


def build_camp():
    """
    Build a campaign input file for the DTK using emod_api. 
    """
    import emod_api.campaign as camp
    import emod_api.interventions.outbreak as ob 

    print(f"Telling emod-api to use {manifest.schema_file} as schema.")
    camp.set_schema( manifest.schema_file )

    def seed():
        #ob.seed( camp, Start_Day=1, Coverage=0.01, Target_Props="Geographic:A", Tot_Rep=20, Rep_Interval=365, Honor_Immunity=True )
        # 1 :: AllPlaces :: 50.0% :: OutbreakIndividual
        ob.seed( camp, Start_Day=2, Coverage=0.5, Honor_Immunity=False )

        # 730(x10/_365) :: AllPlaces :: 0.5% :: OutbreakIndividual
        ob.seed( camp, Start_Day=730, Coverage=0.005, Tot_Rep=10, Rep_Interval=365, Honor_Immunity=False )
    seed()

    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    event = tv.new_triggered_intervention(camp, start_day=20*365, triggers=['Births'], coverage=1.0, node_ids=None, property_restrictions_list=[], co_event=None)
    #camp.add( event )
    event = tv.new_scheduled_intervention(camp, start_day=5*365, coverage=1.0, node_ids=None, property_restrictions_list=[], co_event=None)
    #camp.add( event )

    def seasonal_forcing_go():
        # seasonal forcing
        # G-O method
        import emod_api.interventions.node_multiplier as nim
        nim_iv = nim.new_intervention( camp, new_infectivity=0.0, profile="TRAP", rise_dur=227, peak_dur=19, fall_dur=11 )
        #nim_iv.Transmission_Route = "ENVIRONMENTAL"

        import emod_api.interventions.common as comm
        event = comm.ScheduledCampaignEvent( camp, Start_Day=1, Intervention_List=[nim_iv], Number_Repetitions=-1, Timesteps_Between_Repetitions=365 )
        camp.add( event )
    seasonal_forcing_go()

    def give_vax( start_year, age ):
         import emodpy_typhoid.interventions.typhoid_vaccine as tv
         event = tv.new_triggered_intervention(camp, start_day=(start_year-base_year)*365, triggers=['Births'], coverage=0.85, node_ids=None, property_restrictions_list=[], co_event="Vaccinated")
         # TBD: use common.TriggeredCampaignEvent to use the delay. The above doesn't have delays.
         camp.add( event )
    give_vax( start_year=2017, age=0.75 )

    return camp


def build_demog():
    """
    Build a demographics input file for the DTK using emod_api. 
    """
    import emodpy_typhoid.demographics.TyphoidDemographics as Demographics # OK to call into emod-api

    demog = Demographics.from_template_node( lat=0, lon=0, pop=initial_pop, name=1, forced_id=1 )
    #wb_births_df = pd.read_csv( manifest.world_bank_dataset )
    #demog.SetEquilibriumVitalDynamicsFromWorldBank( wb_births_df=wb_births_df, country='Chile', year=1960 ) # 1960 just coz it's earliest
    demog.SetInitialAgeLikeSubSaharanAfrica()
    inflection_year = 1960
    #demog.SetFertilityOverTimeFromParams( years_region1=40, years_region2=(122-40), start_rate=0.025, inflection_rate=0.025, end_rate=0.007 )
    yrs_region1 = inflection_year-base_year
    yrs_region2 = max((sim_years-yrs_region1),0)
    
    #demog.SetFertilityOverTimeFromParams( years_region1=yrs_region1, years_region2=yrs_region2, start_rate=0.1662, inflection_rate=0.1662, end_rate=0.0521 )
    # 1917-1960( 43 years): high fert -- for typhoid, demog file should have absolute year values in it.
    # years_region1=1960 (ish)
    # years_region2=2015-1960=55
    # stays at low value from 2017 to end
    demog.SetFertilityOverTimeFromParams( years_region1=yrs_region1+base_year, years_region2=55, start_rate=0.1662, inflection_rate=0.1662, end_rate=0.0521 )
    demog.SetMortalityOverTimeFromData( manifest.mortality_data, 0 )

    full_hint_matrix = {
            "contact":  {
                "Matrix":  
                [
                    [ 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0 ]
                ]
            }
            ,
            "environmental" : {
                "Matrix": 
                [
                    [ 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0 ],
                    [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ]
                ]
            }
        }

    """
    demog.AddIndividualPropertyAndHINT(
            Property="Geographic",
            Values=[ "A", "B", "C", "D", "E", "F", "G", "H", "I" ],
            InitialDistribution=[ 0.11111,  0.11111, 0.11111, 0.11111, 0.11111, 0.11111, 0.11111, 0.11111, 0.11112],
            TransmissionMatrix=full_hint_matrix
        )
    """

    return demog


def run_test():
    # Create a platform
    # Show how to dynamically set priority and node_group
    platform = Platform("SLURM", node_group="idm_48cores", priority="Highest") 

    task = EMODTask.from_default2(config_path="config_from_py.json", eradication_path=manifest.eradication_path, campaign_builder=build_camp, demog_builder=build_demog, schema_path=manifest.schema_file, param_custom_cb=set_param_fn, ep4_custom_cb=None)
    #task = EMODTask.from_files(config_path="config_comps_ref.json", eradication_path=manifest.eradication_path, campaign_path="campaign_routine_exp.json", demographics_paths=["TestDemographics_Mystery_Fert.json"], ep4_path=None)

    print("Adding asset dir...")
    task.common_assets.add_directory(assets_directory=manifest.reporters, relative_path="reporter_plugins")

    task.set_sif( manifest.sif )

    # Create simulation sweep with builder
    builder = SimulationBuilder()
    builder.add_sweep_definition( update_sim_random_seed, range(10) )

    # create experiment from builder
    experiment  = Experiment.from_builder(builder, task, name="Typhoid Blantyre emodpy") 
    # The last step is to call run() on the ExperimentManager to run the simulations.
    experiment.run(wait_until_done=True, platform=platform)

    task.handle_experiment_completion( experiment )

    # download and plot some stuff.
    EMODTask.get_file_from_comps( experiment.uid, [ "InsetChart.json", "SpatialOutput_Prevalence.bin" ] )
    task.cache_experiment_metadata_in_sql( experiment.uid )
    import emod_api.channelreports.plot_icj_means as plotter
    chan_data = plotter.collect( str( experiment.uid ), "Infected" )
    plotter.display( chan_data, False, "Infected", str( experiment.uid ) )
    

if __name__ == "__main__":
    #import emod_typhoid.bootstrap as dtk
    #dtk.setup( manifest.model_dl_dir )
    
    run_test()
