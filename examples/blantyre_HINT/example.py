#!/usr/bin/env python

import pandas as pd
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
emodpy.emod_task.dev_mode = True

import manifest

def update_sim_bic(simulation, value):
    simulation.task.config.parameters.Base_Infectivity_Constant = value*0.1
    return {"Base_Infectivity": value}

def update_sim_random_seed(simulation, value):
    #simulation.task.config.parameters.Run_Number = value
    return {"Run_Number": value}

def set_param_fn( config ):
    # sim nature, size and scope
    config.parameters.Simulation_Type = "TYPHOID_SIM"
    #config.parameters.Simulation_Type = "GENERIC_SIM"
    #config.parameters.Enable_Environmental_Route = 1 # This should be implicit with TYPHOID_SIM; Fix in C++/G-O
    config.parameters.Simulation_Duration = 83*365.0
    #config.parameters.Enable_Skipping = 1  
    #config.parameters.Base_Individual_Sample_Rate = 0.2

    # demographics
    config.parameters.x_Birth = 1.1 # just to add some additional fertility

    #config.parameters.Enable_Birth = 0 # temporary
    #config.parameters.Minimum_End_Time = 90 
    # cover up for default bugs in schema

    #Comment some things out while doing GENERIC_SIM testing
    config.parameters.Base_Year = 1917 # to 1960
    config.parameters.Inset_Chart_Reporting_Start_Year = 1917 
    config.parameters.Inset_Chart_Reporting_Stop_Year = 2000
    config.parameters.Report_Typhoid_ByAgeAndGender_Start_Year = 2001
    config.parameters.Report_Typhoid_ByAgeAndGender_Stop_Year = 2002
    ##config.parameters.Infectious_Period_Exponential = 10
    ##config.parameters.Incubation_Period_Constant = 10
    ##config.parameters.Base_Infectivity_Constant = 1


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

    #event = ob.new_intervention( camp, timestep=1, cases=1000 )
    #camp.add( event )
    #ob.seed( camp, Start_Day=1, Coverage=0.01, Target_Props="Geographic:A", Tot_Rep=20, Rep_Interval=365, Honor_Immunity=True )
    # 1 :: AllPlaces :: 50.0% :: OutbreakIndividual
    ob.seed( camp, Start_Day=1, Coverage=0.5, Honor_Immunity=False )

    # 730(x10/_365) :: AllPlaces :: 0.5% :: OutbreakIndividual
    ob.seed( camp, Start_Day=730, Coverage=0.005, Tot_Rep=10, Rep_Interval=365, Honor_Immunity=False )

    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    event = tv.new_triggered_intervention(camp, start_day=20*365, triggers=['Births'], coverage=1.0, node_ids=None, property_restrictions_list=[], co_event=None)
    #camp.add( event )
    event = tv.new_scheduled_intervention(camp, start_day=5*365, coverage=1.0, node_ids=None, property_restrictions_list=[], co_event=None)
    #camp.add( event )

    def seasonal_forcing_go():
        # seasonal forcing
        # G-O method
        import emod_api.interventions.node_multiplier as nim
        nim_iv = nim.new_intervention( camp, new_infectivity=2.0, profile="TRAP", rise_dur=28, peak_dur=190, fall_dur=100 )
        #nim_iv.Transmission_Route = "ENVIRONMENTAL"

        import emod_api.interventions.common as comm
        event = comm.ScheduledCampaignEvent( camp, Start_Day=1, Intervention_List=[nim_iv], Number_Repetitions=-1, Timesteps_Between_Repetitions=365 )
        camp.add( event )
    #seasonal_forcing_go()

    return camp

def build_demog():
    """
    Build a demographics input file for the DTK using emod_api. 
    """
    import emodpy_typhoid.demographics.TyphoidDemographics as Demographics # OK to call into emod-api

    demog = Demographics.from_template_node( lat=0, lon=0, pop=16000, name=1, forced_id=1 )
    wb_births_df = pd.read_csv( manifest.world_bank_dataset )
    demog.SetEquilibriumVitalDynamicsFromWorldBank( wb_births_df=wb_births_df, country='Chile', year=1960 ) # 1960 just coz it's earliest

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
    builder.add_sweep_definition( update_sim_random_seed, range(1) )

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
