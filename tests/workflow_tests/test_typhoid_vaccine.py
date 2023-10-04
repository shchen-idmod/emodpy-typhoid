import json
import os
import sys
import unittest
from functools import partial
from glob import glob

import numpy
import numpy as np
import pandas as pd
from emodpy.emod_task import EMODTask
from idmtools.builders import SimulationBuilder
from idmtools.core import ItemType
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import manifest

BASE_YEAR = 2005
SIMULATION_DURATION_IN_YEARS = 20
CAMP_START_YEAR = 2015


def year_to_days(year):
    return (year - BASE_YEAR) * 365


def compare(a, b):
    pass


def compare_infected_before_vax(self, a, b):
    a_infected_before_vax = a.loc[a['Time Of Report (Year)'].astype(int) <= CAMP_START_YEAR]
    a_list = \
        a_infected_before_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
            ['Time Of Report (Year)', 'Age']).sum()[
            'Infected'].tolist()
    b_infected_before_vax = b.loc[b['Time Of Report (Year)'].astype(int) <= CAMP_START_YEAR]
    b_list = \
        b_infected_before_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
            ['Time Of Report (Year)', 'Age']).sum()[
            'Infected'].tolist()
    # validate before vax starts, all simulations has same infected number
    self.assertListEqual(a_list, b_list)


def compare_infected_after_vax(self, a, b):
    a_infected_after_vax = a.loc[a['Time Of Report (Year)'].astype(int) > CAMP_START_YEAR]
    a_list = \
        a_infected_after_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
            ['Time Of Report (Year)', 'Age']).sum()[
            'Infected'].tolist()
    b_infected_after_vax = b.loc[b['Time Of Report (Year)'].astype(int) > CAMP_START_YEAR]
    b_list = \
        b_infected_after_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
            ['Time Of Report (Year)', 'Age']).sum()[
            'Infected'].tolist()
    self.assertTrue(sum(a_list) >= sum(b_list))

def compare_infected_after_vax_age_15(self, a, b):
    a_infected_after_vax = a.loc[a['Time Of Report (Year)'].astype(int) > CAMP_START_YEAR]
    b_infected_after_vax = b.loc[b['Time Of Report (Year)'].astype(int) > CAMP_START_YEAR]
    # validate after vax starts, total infected number of age groups from 0-15 from a is always greater than in b's
    first_15_age_groups_infected_a = a_infected_after_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
    ['Time Of Report (Year)', 'Age']).sum().head(15).iloc[:, 0].tolist()
    first_15_age_groups_infected_b = b_infected_after_vax[['Time Of Report (Year)', 'Infected', "Age"]].groupby(
        ['Time Of Report (Year)', 'Age']).sum().head(15).iloc[:, 0].tolist()
    self.assertTrue(sum(first_15_age_groups_infected_a) >= sum(first_15_age_groups_infected_b))


class TyphoidVaxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import emod_typhoid.bootstrap as dtk
        dtk.setup(manifest.model_dl_dir)

    def setUp(self):
        self.platform = Platform("SLURM2")
        self.case_name = os.path.basename(__file__) + "--" + self._testMethodName

    def print_params(self):
        """
        Just a useful convenience function for the user.
        """

    def set_param_fn(self, config):
        config.parameters.Simulation_Type = "TYPHOID_SIM"
        config.parameters.Simulation_Duration = SIMULATION_DURATION_IN_YEARS * 365.0
        config.parameters.Base_Individual_Sample_Rate = 0.2

        config.parameters.Base_Year = BASE_YEAR
        config.parameters.Inset_Chart_Reporting_Start_Year = 2010
        config.parameters.Inset_Chart_Reporting_Stop_Year = 2020
        config.parameters.Enable_Demographics_Reporting = 0
        config.parameters.Report_Typhoid_ByAgeAndGender_Start_Year = 2010
        config.parameters.Report_Typhoid_ByAgeAndGender_Stop_Year = 2020
        config.parameters.Demographics_Filenames = [
            "TestDemographics_pak_updated.json"
        ]
        config.parameters.Age_Initialization_Distribution_Type = "DISTRIBUTION_COMPLEX"
        config.parameters.Death_Rate_Dependence = "NONDISEASE_MORTALITY_BY_YEAR_AND_AGE_FOR_EACH_GENDER"
        config.parameters.Birth_Rate_Dependence = "INDIVIDUAL_PREGNANCIES_BY_AGE_AND_YEAR"
        # when using 2018 binary
        import emodpy_typhoid.config as config_utils
        config_utils.cleanup_for_2018_mode(config)
        return config

    def build_camp(self, start_day_offset=1, vax_eff=0.82):
        """
        Build a campaign input file for the DTK using emod_api.
        """
        import emod_api.campaign as camp
        import emod_api.interventions.outbreak as ob

        print(f"Telling emod-api to use {manifest.schema_file} as schema.")
        camp.set_schema(manifest.schema_file)

        for x in range(10):
            event = ob.new_intervention(camp, timestep=1 + x, cases=1)
            camp.add(event)

        import emodpy_typhoid.interventions.typhoid_vaccine as tv
        import emod_api.interventions.common as comm
        ria = tv.new_routine_immunization(camp,
                                          efficacy=vax_eff,
                                          start_day=year_to_days(CAMP_START_YEAR) + start_day_offset
                                          )
        camp.add(ria)
        return camp

    def build_camp1(self, start_day_offset=1, vax_eff=0.82):
        """
        Build a campaign input file for the DTK using emod_api.
        """
        import emod_api.campaign as camp
        import emod_api.interventions.outbreak as ob

        print(f"Telling emod-api to use {manifest.schema_file} as schema.")
        camp.set_schema(manifest.schema_file)

        for x in range(10):
            event = ob.new_intervention(camp, timestep=1 + x, cases=1)
            camp.add(event)

        import emodpy_typhoid.interventions.typhoid_vaccine as tv
        import emod_api.interventions.common as comm
        tv_iv = tv.new_vax(camp,
                           efficacy=vax_eff
                           )
        one_time_campaign = comm.ScheduledCampaignEvent(camp,
                                                        Start_Day=year_to_days(CAMP_START_YEAR) + start_day_offset,
                                                        Intervention_List=[tv_iv],
                                                        Demographic_Coverage=0.72,
                                                        Target_Age_Min=0.75,
                                                        Target_Age_Max=15
                                                        )
        camp.add(one_time_campaign)

        return camp

    def build_demog(self):
        """
        Build a demographics input file for the DTK using emod_api.
        """
        import emodpy_typhoid.demographics.TyphoidDemographics as Demographics  # OK to call into emod-api

        demog = Demographics.from_template_node(lat=0, lon=0, pop=10000, name=1, forced_id=1)
        wb_births_df = pd.read_csv(manifest.world_bank_dataset)
        demog.SetEquilibriumVitalDynamicsFromWorldBank(wb_births_df=wb_births_df, country='Chile', year=2005)
        return demog

    def test_new_routine_immunization(self):
        numpy.random.seed(0)
        self.print_params()
        task = EMODTask.from_default2(config_path="config.json", eradication_path=manifest.eradication_path,
                                      campaign_builder=self.build_camp, demog_builder=None,
                                      schema_path=manifest.schema_file, param_custom_cb=self.set_param_fn,
                                      ep4_custom_cb=None)

        # print("Adding asset dir...")
        task.common_assets.add_asset("../../examples/vaccination/Assets/TestDemographics_pak_updated.json")
        task.set_sif(manifest.sif)

        # Create simulation sweep with builder
        builder = SimulationBuilder()

        # builder.add_sweep_definition( update_sim_random_seed, range(1) )
        def update_campaign_efficacy(simulation, value):
            build_campaign_partial = partial(self.build_camp, vax_eff=value)
            simulation.task.create_campaign_from_callback(build_campaign_partial)
            return {"vax_efficacy": value}

        def update_campaign_start(simulation, value):
            build_campaign_partial = partial(self.build_camp, start_day=value)
            simulation.task.create_campaign_from_callback(build_campaign_partial)
            return {"campaign_start_day": value}

        vax_effs = np.linspace(0, 1.0, 3)  # 0.0, 0.5, 1 (total 3 sims)
        builder.add_sweep_definition(update_campaign_efficacy, vax_effs)
        # start_days = np.linspace(1, 3651, 11)  # 1, 366, etc.
        # builder.add_sweep_definition(update_campaign_start, start_days)

        # create experiment from builder
        experiment = Experiment.from_builder(builder, task, name=self.case_name)
        # The last step is to call run() on the ExperimentManager to run the simulations.
        experiment.run(wait_until_done=True, platform=self.platform)
        #exp_id = '5e2c8522-d962-ee11-92fc-f0921c167864'
        #experiment = self.platform.get_item(exp_id, item_type=ItemType.EXPERIMENT)
        task.handle_experiment_completion(experiment)
        task.get_file_from_comps(experiment.uid, ["ReportTyphoidByAgeAndGender.csv"])
        # Get downloaded local ReportEventRecorder.csv file path for all simulations
        reporteventrecorder_downloaded = list(
            glob(os.path.join(experiment.id, "**/ReportTyphoidByAgeAndGender.csv"), recursive=True))

        # ---------------------------------------------
        # Test birth rate and death rate to match world bank birth rate: (should be same as birth_rate)
        infected_by_age = pd.DataFrame()
        df_list = []
        for i in range(len(reporteventrecorder_downloaded)):
            # read ReportEventRecorder.csv from each sim
            df = pd.read_csv(reporteventrecorder_downloaded[i])
            df.columns = df.columns.to_series().apply(lambda x: x.strip())
            df_list.append(df)

        import itertools
        for a, b in itertools.combinations(df_list, 2):
            infected_by_age[i] = df[[df.columns.values[0], 'Infected', "Age"]].groupby('Age').sum()["Infected"].tolist()
            compare_infected_before_vax(self, a, b)

        # Since df_list is saved with simulation with order of vax_eff from 0 to 1,
        # i.e first df in df_list is corresponding to vax_eff = 0, and last df in df_list is for sim with cax_eff = 1
        # we want to make sure after vax ingested, infected number for sim with vax_eff=0 should always greater than sim with vax_eff = 1
        # note, I did not compare every single sim since occasionally there maybe some outliers for comparison for sims in middle
        compare_infected_after_vax(self, df_list[0], df_list[len(df_list) - 1])

    def test_campaign_immunization(self):
        numpy.random.seed(0)
        self.print_params()
        task = EMODTask.from_default2(config_path="config.json", eradication_path=manifest.eradication_path,
                                      campaign_builder=self.build_camp1, demog_builder=None,
                                      schema_path=manifest.schema_file, param_custom_cb=self.set_param_fn,
                                      ep4_custom_cb=None)

        # print("Adding asset dir...")
        task.common_assets.add_asset("../../examples/vaccination/Assets/TestDemographics_pak_updated.json")
        task.set_sif(manifest.sif)

        # Create simulation sweep with builder
        builder = SimulationBuilder()

        # builder.add_sweep_definition( update_sim_random_seed, range(1) )
        def update_campaign_efficacy(simulation, value):
            build_campaign_partial = partial(self.build_camp1, vax_eff=value)
            simulation.task.create_campaign_from_callback(build_campaign_partial)
            return {"vax_efficacy": value}

        vax_effs = np.linspace(0, 1.0, 3)  # 0.0, 0.5, 1 (total 3 sims)
        builder.add_sweep_definition(update_campaign_efficacy, vax_effs)
        # start_days = np.linspace(1, 3651, 11)  # 1, 366, etc.
        # builder.add_sweep_definition(update_campaign_start, start_days)

        # create experiment from builder
        experiment = Experiment.from_builder(builder, task, name=self.case_name)
        # The last step is to call run() on the ExperimentManager to run the simulations.
        experiment.run(wait_until_done=True, platform=self.platform)
        #exp_id = '66bf7b07-fb62-ee11-92fc-f0921c167864'
        #experiment = self.platform.get_item(exp_id, item_type=ItemType.EXPERIMENT)
        task.handle_experiment_completion(experiment)
        task.get_file_from_comps(experiment.uid, ["ReportTyphoidByAgeAndGender.csv"])
        # Get downloaded local ReportEventRecorder.csv file path for all simulations
        reporteventrecorder_downloaded = list(
            glob(os.path.join(experiment.id, "**/ReportTyphoidByAgeAndGender.csv"), recursive=True))

        # ---------------------------------------------
        # Test birth rate and death rate to match world bank birth rate: (should be same as birth_rate)
        infected_by_age = pd.DataFrame()
        df_list = []
        for i in range(len(reporteventrecorder_downloaded)):
            # read ReportEventRecorder.csv from each sim
            df = pd.read_csv(reporteventrecorder_downloaded[i])
            df.columns = df.columns.to_series().apply(lambda x: x.strip())
            df_list.append(df)

        import itertools
        for a, b in itertools.combinations(df_list, 2):
            infected_by_age[i] = df[[df.columns.values[0], 'Infected', "Age"]].groupby('Age').sum()["Infected"].tolist()
            compare_infected_before_vax(self, a, b)

        # Since df_list is saved with simulation with order of vax_eff from 0 to 1,
        # i.e first df in df_list is corresponding to vax_eff = 0, and last df in df_list is for sim with cax_eff = 1
        # we want to make sure after vax ingested, infected number for sim with vax_eff=0 should always greater than sim with vax_eff = 1
        # note, I did not compare every single sim since occasionally there maybe some outliers for comparison for sims in middle
        compare_infected_after_vax_age_15(self, df_list[0], df_list[len(df_list) - 1])

