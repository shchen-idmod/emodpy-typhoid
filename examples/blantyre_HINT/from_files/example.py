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

import manifest

def update_sim_random_seed(simulation, value):
    return {"Run_Number": value}

def run():
    # Create a platform
    # Show how to dynamically set priority and node_group
    platform = Platform("SLURM", node_group="idm_48cores", priority="Highest") 

    task = EMODTask.from_files(config_path="config_comps_ref.json", eradication_path=manifest.eradication_path, campaign_path="campaign_routine_exp.json", demographics_paths=["TestDemographics_Mystery_Fert.json"], ep4_path=None)

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
    run()
