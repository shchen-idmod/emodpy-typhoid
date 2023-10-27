#!/usr/bin/env python

import pandas as pd
import numpy as np # just for linspace
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
import emod_api.interventions.common as comm 
#comm.old_adhoc_trigger_style = False

import manifest

BASE_YEAR=2010
SIMULATION_DURATION_IN_YEARS=12
CAMP_START_YEAR=2019

def update_sim_bic(simulation, value):
    simulation.task.config.parameters.Base_Infectivity_Constant = value*0.1
    return {"Base_Infectivity": value}

def update_sim_random_seed(simulation, value):
    simulation.task.config.parameters.Run_Number = value
    return {"Run_Number": value}

def year_to_days( year ):
    return ( (year-BASE_YEAR)*365 )

def set_param_fn( config ):
    config.parameters.Simulation_Type = "TYPHOID_SIM"
    config.parameters.Simulation_Duration = SIMULATION_DURATION_IN_YEARS*365.0
    #config.parameters.Base_Individual_Sample_Rate = 0.2

    #config.parameters.Enable_Birth = 0 # temporary
    #config.parameters.Minimum_End_Time = 90 
    # cover up for default bugs in schema
    config.parameters.Base_Year = BASE_YEAR
    config.parameters.Inset_Chart_Reporting_Start_Year = 1900 
    config.parameters.Inset_Chart_Reporting_Stop_Year = 2050 
    config.parameters.Enable_Demographics_Reporting = 0 
    config.parameters.Enable_Property_Output = 1 
    config.parameters.Report_Event_Recorder_Events = [ "VaccineDistributed", "PropertyChange"]
    config.parameters["Listed_Events"] = [ "VaccineDistributed" ] # old school
    #config.parameters.Typhoid_Immunity_Memory = 36500
    #config.parameters.Config_Name = "149_Typhoid"

    config.parameters.Report_Typhoid_ByAgeAndGender_Start_Year = 2010
    config.parameters.Report_Typhoid_ByAgeAndGender_Stop_Year = 2050
    config.parameters.Typhoid_3year_Susceptible_Fraction = 0
    config.parameters.Typhoid_6month_Susceptible_Fraction = 0
    config.parameters.Typhoid_6year_Susceptible_Fraction = 0
    config.parameters.Typhoid_Acute_Infectiousness = 13435
    config.parameters.Typhoid_Carrier_Probability = 0.108
    config.parameters.Typhoid_Carrier_Removal_Year = 2500
    config.parameters.Typhoid_Chronic_Relative_Infectiousness = 0.241
    config.parameters.Typhoid_Contact_Exposure_Rate = 0.06918859049226553
    config.parameters.Typhoid_Environmental_Exposure_Rate = 0.06169346985005757
    config.parameters.Typhoid_Environmental_Cutoff_Days = 157.20690133538764
    config.parameters.Typhoid_Environmental_Peak_Start = 355.0579483941714
    config.parameters.Typhoid_Environmental_Ramp_Down_Duration = 112.30224910440123
    config.parameters.Typhoid_Environmental_Ramp_Up_Duration = 39.540475369174146
    config.parameters.Typhoid_Exposure_Lambda = 7.0
    config.parameters.Typhoid_Prepatent_Relative_Infectiousness = 0.5
    config.parameters.Typhoid_Protection_Per_Infection = 0.98
    config.parameters.Typhoid_Subclinical_Relative_Infectiousness = 1
    config.parameters.Typhoid_Symptomatic_Fraction = 0.07

    #config.parameters.x_Birth = 1.2

    # when using 2018 binary
    import emodpy_typhoid.config as config_utils
    config_utils.cleanup_for_2018_mode( config )
    return config


def build_camp( start_day_offset=1, vax_eff = 0.82 ):
    """
    Build a campaign input file for the DTK using emod_api. 
    """
    import emod_api.campaign as camp
    import emod_api.interventions.outbreak as ob 

    print(f"Telling emod-api to use {manifest.schema_file} as schema.")
    camp.set_schema( manifest.schema_file )

    for x in range( 10 ):
        event = ob.new_intervention( camp, timestep=1+x, cases=1 )
        camp.add( event )

    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    import emod_api.interventions.common as comm 
    ria = tv.new_routine_immunization( camp,
            efficacy=vax_eff,
            start_day=year_to_days( CAMP_START_YEAR )+start_day_offset
        )

    notification_iv = comm.BroadcastEvent( camp, "VaccineDistributed" )
    #event = comm.triggered_campaign_event_with_optional_delay( camp, start_day=1, intervention=[tv_iv,notification_iv], triggers=["Births"], delay=delay_dict )
    camp.add( ria )

    tv_iv = tv.new_vax( camp,
            efficacy=vax_eff 
        )
    one_time_campaign = comm.ScheduledCampaignEvent( camp,
                Start_Day=year_to_days( CAMP_START_YEAR )+start_day_offset,
                Intervention_List=[tv_iv,notification_iv],
                Demographic_Coverage=0.72,
                Target_Age_Min=0.75,
                Target_Age_Max=15
        )
    camp.add( one_time_campaign )

    def migrate():
        """
        Use PropertyValueChanger to move some fraction between Rural and Urban over time.
        """

        def two_step():
            rural_to_urban_pvc = comm.PropertyValueChanger( camp,
                Target_Property_Key="Region",
                Target_Property_Value="Urban",
                Maximum_Duration=30,
                Revert=1,
            )
            #rural_to_urban_pvc = comm.PropertyValueChanger( camp, ... )
            event = comm.ScheduledCampaignEvent( camp,
                    Start_Day=t,
                    Intervention_List=[rural_to_urban_pvc],
                    Demographic_Coverage=0.1,
                    Property_Restrictions = "Region:Rural"
                    #,Target_Age_Min=0.75,
                    #,Target_Age_Max=15
                )
            camp.add( event )
            """
            # 1% Urban->Rural
            comm.change_individual_property( camp,
                    target_property_name="Region",
                    target_property_value="Rural",
                    start_day=t, coverage=0.01,
                    ip_restrictions="Region:Urban" )
            """
           
        def one_step():
            # 1% Rural->Urban
            comm.change_individual_property( camp,
                    target_property_name="Region",
                    target_property_value="Urban",
                    start_day=t, coverage=0.1, 
                    ip_restrictions="Region:Rural" )

        for t in np.linspace( 1, SIMULATION_DURATION_IN_YEARS*365, 20 ):
            two_step()

        #for t in np.linspace( 10*365, SIMULATION_DURATION_IN_YEARS*365, 3 ):

    #migrate()
    return camp

def build_demog():
    """
    Build a demographics input file for the DTK using emod_api. 
    """
    import emodpy_typhoid.demographics.TyphoidDemographics as Demographics # OK to call into emod-api

    demog = Demographics.from_template_node( lat=0, lon=0, pop=10000, name=1, forced_id=1 )
    # We're getting all our demographics from a static file overlay.

    """
    # This doesn't work right now but still want to leave in example of what we want to be able to do soon.
    demog.AddAgeDependentTransmission( 
            Age_Bin_Edges_In_Years = [0, 5, 20, 60, -1],
            TransmissionMatrix = [
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 1.0, 1.0]
            ]
    )
    """
    # 80% rural, 20% urban.
    demog.AddIndividualPropertyAndHINT( Property="Region",
            Values = [ "Rural", "Urban" ],
            InitialDistribution = [ 0.8, 0.2 ],
            TransmissionMatrix = [
                            [ 1, 0.1 ],
                            [ 0.1, 1 ]
                        ],
            EnviroTransmissionMatrix = [
                            [ 1, 0.1 ],
                            [ 0.1, 1 ]
                        ]
        )

    return demog


def run_test():
    # Create a platform
    # Show how to dynamically set priority and node_group
    platform = Platform("SLURM", node_group="idm_48cores", priority="Highest") 

    task = EMODTask.from_default2(config_path="config.json", eradication_path=manifest.eradication_path, campaign_builder=build_camp, demog_builder=build_demog, schema_path=manifest.schema_file, param_custom_cb=set_param_fn, ep4_custom_cb=None)
    # normally we don't force-set parameters at this point
    task.config.parameters.Demographics_Filenames = [  "demographics.json", "TestDemographics_pak_updated.json" ]
    task.config.parameters.Death_Rate_Dependence = "NONDISEASE_MORTALITY_BY_YEAR_AND_AGE_FOR_EACH_GENDER"
    task.config.parameters.Birth_Rate_Dependence = "INDIVIDUAL_PREGNANCIES_BY_AGE_AND_YEAR"
    task.common_assets.add_directory(assets_directory=manifest.assets_input_dir)

    task.set_sif( manifest.sif )

    # Create simulation sweep with builder
    builder = SimulationBuilder()
    #builder.add_sweep_definition( update_sim_random_seed, range(1) )
    def update_campaign_efficacy(simulation, value):
        build_campaign_partial = partial(build_camp, vax_eff=value)
        simulation.task.create_campaign_from_callback(build_campaign_partial)
        return {"vax_efficacy": value}
    def update_campaign_start(simulation, value):
        build_campaign_partial = partial(build_camp, start_day=value)
        simulation.task.create_campaign_from_callback(build_campaign_partial)
        return {"campaign_start_day": value}

    vax_effs = np.linspace(0,1.0,3) # 0.0, 0.5, 1.0
    builder.add_sweep_definition( update_campaign_efficacy, vax_effs )
    builder.add_sweep_definition( update_sim_random_seed, range(5) ) # keep at 1 for smoketesting
    #start_day_offsets = np.linspace(0,60,7) # 1, 366, etc.
    #builder.add_sweep_definition( update_campaign_start, start_day_offsets )

    # create experiment from builder
    experiment  = Experiment.from_builder(builder, task, name="Typhoid Vax 101") 
    # The last step is to call run() on the ExperimentManager to run the simulations.
    experiment.run(wait_until_done=True, platform=platform)

    task.handle_experiment_completion( experiment )

    # download and plot some stuff.
    EMODTask.get_file_from_comps( experiment.uid, [ "InsetChart.json" ] )
    task.cache_experiment_metadata_in_sql( experiment.uid )
    import matplotlib
    matplotlib.use( "TkAgg" )
    import emod_api.channelreports.plot_icj_means as plotter
    chan_data = plotter.collect( str( experiment.uid ), "Infected", tag="vax_efficacy=SWEEP" )
    plotter.display( chan_data, False, "Infected", str( experiment.uid ) )
    

if __name__ == "__main__":
    import emod_typhoid.bootstrap as dtk
    dtk.setup( manifest.model_dl_dir )
    
    run_test()
