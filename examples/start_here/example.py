#!/usr/bin/env python

import pandas as pd
import pathlib # for a join
from functools import partial

# idmtools ...
from idmtools.assets import Asset, AssetCollection  #
from idmtools.builders import SimulationBuilder
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations
from idmtools_platform_comps.utils.python_requirements_ac.requirements_to_asset_collection import RequirementsToAssetCollection
from idmtools_models.templated_script_task import get_script_wrapper_unix_task
from config_sweep_builders import get_sweep_builders
# emodpy
from emodpy.emod_task import EMODTask
import emodpy.emod_task

import params

emodpy.emod_task.dev_mode = True

import manifest

def update_sim_bic(simulation, value):
    simulation.task.config.parameters.Base_Infectivity_Constant = value*0.1
    return {"Base_Infectivity": value}

def update_sim_random_seed(simulation, value):
    simulation.task.config.parameters.Run_Number = value
    return {"Run_Number": value}

def set_param_fn( config ):
    config.parameters.Simulation_Type = "TYPHOID_SIM"
    config.parameters.Simulation_Duration = 365.0
    config.parameters.Base_Individual_Sample_Rate = 1
    config.parameters.Base_Infectivity = 0.3
    #config.parameters.Enable_Birth = 0 # temporary
    #config.parameters.Minimum_End_Time = 90 
    # cover up for default bugs in schema
    config.parameters.Inset_Chart_Reporting_Start_Year = 1900 
    config.parameters.Inset_Chart_Reporting_Stop_Year = 2050 
    config.parameters.Enable_Demographics_Reporting = 0 
    config.parameters.Node_Contagion_Decay_Rate = 0.33

    # when using 2018 binary
    import emodpy_typhoid.config as config_utils
    config_utils.cleanup_for_2018_mode( config )

    return config


def build_camp():
    """
    Build a campaign input file for the DTK using emod_api. 
    """
    import emod_api.campaign as camp
    import emod_api.interventions.outbreak as ob 

    print(f"Telling emod-api to use {manifest.schema_file} as schema.")
    camp.set_schema( manifest.schema_file )

    event = ob.new_intervention( camp, timestep=1, cases=1 )
    camp.add( event )

    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    event_vax = tv.new_triggered_intervention(camp, start_day=30,
                                              triggers=['Births'],
                                              coverage=0.85, node_ids=None, property_restrictions_list=[],
                                              co_event="Vaccinated")
    camp.add(event_vax)
    return camp

def build_demog():
    """
    Build a demographics input file for the DTK using emod_api. 
    """
    import emodpy_typhoid.demographics.TyphoidDemographics as Demographics # OK to call into emod-api

    demog = Demographics.from_template_node( lat=0, lon=0, pop=10000, name=1, forced_id=1 )
    wb_births_df = pd.read_csv( manifest.world_bank_dataset )
    demog.SetEquilibriumVitalDynamicsFromWorldBank( wb_births_df=wb_births_df, country='Chile', year=2005 )
    return demog


def run_test(**kwargs):
    # Create a platform
    # Show how to dynamically set priority and node_group
    platform = Platform("SLURM", node_group="idm_48cores", priority="Highest") 

    task = EMODTask.from_default2(config_path="config.json", eradication_path=manifest.eradication_path, campaign_builder=build_camp, demog_builder=build_demog, schema_path=manifest.schema_file, param_custom_cb=set_param_fn, ep4_custom_cb=None)

    print("Adding asset dir...")
    task.common_assets.add_directory(assets_directory=manifest.reporters, relative_path="reporter_plugins")

    task.set_sif( manifest.sif )

    # Create simulation sweep with builder
    kwargs['platform'] = platform
    builders = get_sweep_builders(**kwargs)
    ts = TemplatedSimulations(base_task=task, builders=builders)
    # # create experiment from builder
    experiment = Experiment.from_template(ts, name=params.exp_name)
    experiment.run(wait_until_done=True)
    task.handle_experiment_completion( experiment )

    # download and plot some stuff.
    if experiment.succeeded:
        EMODTask.get_file_from_comps( experiment.uid, [ "InsetChart.json", "ReportTyphoidByAgeAndGender.csv" ], group=True )
        task.cache_experiment_metadata_in_sql( experiment.uid )
        #import emod_api.channelreports.plot_icj_means as plotter
        #chan_data = plotter.collect( str( experiment.uid ), "Infected" )
        #plotter.display( chan_data, False, "Infected", str( experiment.uid ) )
    

if __name__ == "__main__":
    import emod_typhoid.bootstrap as dtk
    dtk.setup( manifest.model_dl_dir )
    #
    run_test()
