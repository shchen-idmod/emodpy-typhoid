#!/usr/bin/env python
import itertools

import numpy as np  # just for linspace
from functools import partial

# idmtools ...
from idmtools.builders import SimulationBuilder
from idmtools.core import ItemType
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment
from idmtools.entities.templated_simulation import TemplatedSimulations


# emodpy
from emodpy.emod_task import EMODTask

import emod_api.interventions.common as comm

import manifest

from emodpy_typhoid.utility.sweeping import ItvFn, set_param, sweep_functions

BASE_YEAR = 2005
SIMULATION_DURATION_IN_YEARS = 20
CAMP_START_YEAR = 2015


def year_to_days(year):
    return ((year - BASE_YEAR) * 365)

def set_param_fn(config):
    config.parameters.Simulation_Type = "TYPHOID_SIM"
    config.parameters.Simulation_Duration = SIMULATION_DURATION_IN_YEARS * 365.0
    config.parameters.Base_Individual_Sample_Rate = 0.2

    config.parameters.Base_Year = BASE_YEAR
    config.parameters.Inset_Chart_Reporting_Start_Year = BASE_YEAR
    config.parameters.Inset_Chart_Reporting_Stop_Year = 2030
    config.parameters.Enable_Demographics_Reporting = 0
    #config.parameters.Enable_Property_Output = 1  # crash
    config.parameters.Report_Event_Recorder_Events = ["VaccineDistributed", "PropertyChange"]
    config.parameters["Listed_Events"] = ["VaccineDistributed"]  # old school

    config.parameters.Report_Typhoid_ByAgeAndGender_Start_Year = 2010
    config.parameters.Report_Typhoid_ByAgeAndGender_Stop_Year = 2030
    config.parameters.Age_Initialization_Distribution_Type = "DISTRIBUTION_COMPLEX"
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
    # config.parameters.x_Birth = 1.2

    # when using 2018 binary
    import emodpy_typhoid.config as config_utils
    config_utils.cleanup_for_2018_mode(config)
    return config


def build_camp():
    import emod_api.campaign as camp

    print(f"Telling emod-api to use {manifest.schema_file} as schema.")
    camp.set_schema(manifest.schema_file)
    import emodpy_typhoid.interventions.outbreak as ob
    ob_event = ob.add_outbreak_individual(start_day=1,
                                          demographic_coverage=0.05,
                                          node_ids=[1],
                                          repetitions= 5,
                                          timesteps_between_repetitions=30,
                                          #ind_property_restrictions=["Region:A"]
                                          )
    camp.add(ob_event)
    return camp


def build_demog():
    """
    Build a demographics input file for the DTK using emod_api. 
    """
    import emodpy_typhoid.demographics.TyphoidDemographics as Demographics  # OK to call into emod-api

    demog = Demographics.from_template_node(lat=0, lon=0, pop=10000, name=1, forced_id=1)
    # We're getting all our demographics from a static file overlay.

    return demog


def add_vax_intervention(campaign, values, min_age=0.75, max_age=15):
    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    print(f"Telling emod-api to use {manifest.schema_file} as schema.")
    campaign.set_schema(manifest.schema_file)
    ria_coverage = 1
    camp_coverage = 1
    if 'coverage' in values:
        ria_coverage = values['coverage']
        camp_coverage = values['coverage']
    else:
        if 'coverage_ria' in values:
            ria_coverage = values['coverage_ria']
        else:
            camp_coverage = values['coverage_camp']

    ria = tv.new_routine_immunization(campaign,
                                      efficacy=values['efficacy'],
                                      constant_period=0,
                                      #decay_constant=values['decay_constant'],
                                      expected_expiration=values['decay_constant'],
                                      start_day=year_to_days(CAMP_START_YEAR) + values['start_day_offset'],
                                      coverage=ria_coverage
                                      )

    notification_iv = comm.BroadcastEvent(campaign, "VaccineDistributed")
    campaign.add(ria)

    tv_iv = tv.new_vax(campaign,
                       efficacy=values['efficacy'],
                       #decay_constant=values['decay_constant'],
                       expected_expiration=values['decay_constant'],
                       constant_period=0
                       )
    one_time_campaign = comm.ScheduledCampaignEvent(campaign,
                                                    Start_Day=year_to_days(CAMP_START_YEAR) + values['start_day_offset'],
                                                    Intervention_List=[tv_iv, notification_iv],
                                                    Demographic_Coverage=camp_coverage,
                                                    Target_Age_Min=min_age,
                                                    Target_Age_Max=max_age
                                                    )
    campaign.add(one_time_campaign)
    return {
        "start_day": values['start_day_offset'],
        'efficacy': values['efficacy'],
        'coverage_ria': ria_coverage,
        'coverage_camp': camp_coverage,
        'decay': values['decay_constant']
    }


def get_sweep_builders(sweep_list, add_vax_fn=add_vax_intervention):
    """
    Build simulation builders.
    Args:
        kwargs: User inputs may overwrite the entries in the block.

    Returns:
        lis of Simulation builders
    """
    builder = SimulationBuilder()
    funcs_list = [[
        ItvFn(add_vax_fn, ce),
        partial(set_param, param='Run_Number', value=x),
    ]
        for ce in sweep_list  # for sweep on sweep_list
        for x in range(5)  # for sweep Run_Number
    ]

    builder.add_sweep_definition(sweep_functions, funcs_list)

    return [builder]


def run( sweep_choice="All" ):
    # Create a platform
    # Show how to dynamically set priority and node_group
    platform = Platform("SLURM", node_group="idm_48cores", priority="Highest")
    #platform = Platform("SLURMStage", node_group="idm_48cores", priority="Highest")

    task = EMODTask.from_default2(config_path="config.json", eradication_path=manifest.eradication_path,
                                  campaign_builder=build_camp, demog_builder=build_demog, schema_path=manifest.schema_file,
                                  param_custom_cb=set_param_fn, ep4_custom_cb=None)
    # normally we don't force-set parameters at this point
    task.config.parameters.Demographics_Filenames = ["demographics.json","TestDemographics_pak_updated.json"]
    task.config.parameters.Death_Rate_Dependence = "NONDISEASE_MORTALITY_BY_YEAR_AND_AGE_FOR_EACH_GENDER"
    task.config.parameters.Birth_Rate_Dependence = "INDIVIDUAL_PREGNANCIES_BY_AGE_AND_YEAR"
    task.common_assets.add_directory(assets_directory=manifest.assets_input_dir)
    task.set_sif(manifest.sif)

    # Create simulation sweep with builder
    def get_sweep_list_from_values(start_day_offset, vax_effs, cov, decay):
        sweep_list = []
        combinations = list(itertools.product(start_day_offset, vax_effs, cov, decay))
        for c in combinations:
            sweep_list.append({'start_day_offset': c[0], 'efficacy': c[1], 'coverage': c[2], 'decay_constant': c[3]})
        return sweep_list

    def get_sweep_list_full():
        start_day_offset = [1]
        vax_effs = np.linspace(0.1, 1.0, 10)
        decay = [1, 365, 3650, 365000]
        cov = np.linspace(start=0.0, stop=1.0, num=5)
        return get_sweep_list_from_values(start_day_offset, vax_effs, cov, decay)

    def get_sweep_list_efficacy():
        start_day_offset = [1]
        vax_effs = np.linspace(0.1, 1.0, 10)
        decay = [3000]
        cov = [1]
        return get_sweep_list_from_values(start_day_offset, vax_effs, cov, decay)

    def get_sweep_list_coverage():
        start_day_offset = [1]
        vax_effs = [1]
        decay = [3000]
        cov = np.linspace(start=0.0, stop=1.0, num=5)
        return get_sweep_list_from_values(start_day_offset, vax_effs, cov, decay)

    def get_sweep_list_coverage_ria():
        start_day_offset = [1]
        vax_effs = [1]
        decay = [3000]
        cov = np.linspace(start=0.0, stop=1.0, num=5)
        combinations = list(itertools.product(start_day_offset, vax_effs, cov, decay))
        sweep_list = []
        for c in combinations:
            sweep_list.append({'start_day_offset': c[0], 'efficacy': c[1], 'coverage_ria': c[2], 'decay_constant': c[3]})
        return sweep_list

    def get_sweep_list_coverage_camp():
        start_day_offset = [1]
        vax_effs = [1]
        decay = [3000]
        cov = np.linspace(start=0.0, stop=1.0, num=5)
        combinations = list(itertools.product(start_day_offset, vax_effs, cov, decay))
        sweep_list = []
        for c in combinations:
            sweep_list.append({'start_day_offset': c[0], 'efficacy': c[1], 'coverage_camp': c[2], 'decay_constant': c[3]})
        return sweep_list

    def get_sweep_list_duration():
        start_day_offset = [1]
        vax_effs = [1]
        decays = [1,365,3650,36500]
        covs = [1.0]

        combinations = list(itertools.product(start_day_offset, vax_effs, covs, decays))
        sweep_list = []
        for c in combinations:
            sweep_list.append({'start_day_offset': c[0], 'efficacy': c[1], 'coverage': c[2], 'decay_constant': c[3]})
        return sweep_list

    def get_sweep_list_from_csv():
        # This is wrong. Just load rows. Code is recreating. But have to stop work for now.
        import pandas as pd
        df = pd.load_csv( manifest.sweep_config )
        raise NotImplemented( "get_sweep_list_from_csv" )

    sweep_selections = {
            "All": get_sweep_list_full,
            "Efficacy": get_sweep_list_efficacy,
            "Coverage": get_sweep_list_coverage,
            "Coverage_RIA": get_sweep_list_coverage_ria,
            "Coverage_Camp": get_sweep_list_coverage_camp,
            "Vax_Duration": get_sweep_list_duration
            }

    if sweep_choice not in sweep_selections.keys():
        raise ValueError( f"{sweep_choice} not found in {sweep_selections.keys()}." )
    sweep_list = sweep_selections[ sweep_choice ]()
    #sweep_list = get_sweep_list_from_csv()
    avi_full_coverage = partial( add_vax_intervention, min_age=0, max_age=125 )
    #builders = get_sweep_builders(sweep_list)
    builders = get_sweep_builders(sweep_list, add_vax_fn=avi_full_coverage)
    # create TemplatedSimulations from task and builders
    ts = TemplatedSimulations(base_task=task, builders=builders)
    # create experiment from TemplatedSimulations
    experiment = Experiment.from_template(ts, name=f"{sweep_choice} Sweep")
    experiment.run(wait_until_done=True, platform=platform)
    task.handle_experiment_completion(experiment)

    # download and plot some stuff.
    EMODTask.get_file_from_comps(experiment.uid, ["InsetChart.json", "ReportTyphoidByAgeAndGender.csv"])
    task.cache_experiment_metadata_in_sql(experiment.uid)
    return str(experiment.uid)

if __name__ == "__main__":
    import emod_typhoid.bootstrap as dtk

    dtk.setup(manifest.model_dl_dir)

    import sys
    run( sys.argv[1] if len(sys.argv)>1 else "Efficacy" )
