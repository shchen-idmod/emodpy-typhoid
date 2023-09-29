import json
import os
import pathlib
import sys
import unittest
from glob import glob

import numpy
import pandas as pd
from emodpy.emod_task import EMODTask
from idmtools.builders import SimulationBuilder
from idmtools.core import ItemType
from idmtools.core.platform_factory import Platform
from idmtools.entities.experiment import Experiment

import emodpy_typhoid.demographics.TyphoidDemographics as TyphoidDemographics

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import manifest


class DemographicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import emod_typhoid.bootstrap as dtk
        dtk.setup(manifest.model_dl_dir)

    def setUp(self):
        self.platform = Platform("SLURM2")
        self.schema_path = manifest.schema_file
        self.eradication = manifest.eradication_path
        self.n_replica = 1
        self.wb_births_df = pd.read_csv(manifest.world_bank_dataset)
        self.place = "Pakistan"
        self.year = 2015
        self.total_sim_year = 10
        self.sim_sample_rate = 0.1

    def tearDown(self) -> None:
        file_to_rem = pathlib.Path("demographics_vita.json")
        file_to_rem.unlink(missing_ok=True)

    def update_sim_bic(self, simulation, value):
        simulation.task.config.parameters.Base_Infectivity_Constant = value * 0.1
        return {"Base_Infectivity": value}

    def update_sim_random_seed(self, simulation, value):
        simulation.task.config.parameters.Run_Number = value
        return {"Run_Number": value}

    def print_params(self):
        """
        Just a useful convenience function for the user.
        """

    def set_param_fn(self, config):
        config.parameters.Simulation_Duration = 365.0 * self.total_sim_year
        config.parameters.Enable_Demographics_Reporting = 0
        config.parameters.Simulation_Type = "TYPHOID_SIM"
        config.parameters.Base_Individual_Sample_Rate = self.sim_sample_rate
        # cover up for default bugs in schema
        config.parameters.Inset_Chart_Reporting_Start_Year = 1900
        config.parameters.Inset_Chart_Reporting_Stop_Year = 2040
        config.parameters.Enable_Demographics_Reporting = 0

        # when using 2018 binary
        import emodpy_typhoid.config as config_utils
        config_utils.cleanup_for_2018_mode(config)
        config.parameters.Report_Event_Recorder_Events = ["Births", "NonDiseaseDeaths", "HappyBirthday"]
        config.parameters.Spatial_Output_Channels = ["Population", "Births"]

        return config

    def build_camp(self):
        """
        Build a campaign input file for the DTK using emod_api.
        """
        import emod_api.campaign as camp
        print(f"Telling emod-api to use {manifest.schema_file} as schema.")
        camp.set_schema(manifest.schema_file)
        return camp

    def build_demog(self):
        """
        Build a demographics input file for the DTK using emod_api.
        """
        input_file = os.path.join("data", "ten_nodes.csv")
        demog = TyphoidDemographics.from_csv(input_file)
        demog.SetEquilibriumVitalDynamicsFromWorldBank(wb_births_df=self.wb_births_df, country='Pakistan', year=2005)
        demog.generate_file("demographics_vita.json")
        return demog

    def test_vd_demog_from_worldbank(self):
        numpy.random.seed(0)
        self.print_params()
        EMODTask.dev_mode = True
        task = EMODTask.from_default2(config_path="config.json", eradication_path=self.eradication,
                                      campaign_builder=self.build_camp, demog_builder=self.build_demog,
                                      schema_path=self.schema_path, param_custom_cb=self.set_param_fn,
                                      ep4_custom_cb=None)
        print("Adding asset dir...")
        task.common_assets.add_directory(assets_directory=manifest.reporters, relative_path="reporter_plugins")

        task.set_sif(manifest.sif)

        # Create simulation sweep with builder
        builder = SimulationBuilder()
        builder.add_sweep_definition(self.update_sim_random_seed, range(10))

        # create experiment from builder
        experiment = Experiment.from_builder(builder, task, name="test_vitaldynamics_demog_from_worldbank")
        experiment.run(wait_until_done=True, platform=self.platform)
        #exp_id = 'fb294ae0-5a5e-ee11-92fc-f0921c167864'
        #experiment = self.platform.get_item(exp_id, item_type=ItemType.EXPERIMENT)
        self.assertTrue(experiment.succeeded, msg=f"Experiment {experiment.uid} failed.\n")

        task.handle_experiment_completion(experiment)
        task.get_file_from_comps(experiment.uid, ["ReportEventRecorder.csv"])
        # Get downloaded local ReportEventRecorder.csv file path for all simulations
        reporteventrecorder_downloaded = list(
            glob(os.path.join(experiment.id, "**/ReportEventRecorder.csv"), recursive=True))

        # ---------------------------------------------
        # Test birth rate and death rate to match world bank birth rate: (should be same as birth_rate)
        birth_count_df = pd.DataFrame()
        death_count_df = pd.DataFrame()
        for i in range(len(reporteventrecorder_downloaded)):
            # read ReportEventRecorder.csv from each sim
            df = pd.read_csv(reporteventrecorder_downloaded[i])
            # Get birth count for each sim. Birth count is total birth row count by Node_ID
            # Note, replace function to replace each 'Births' to 1 to make aggregate easier for groupby and sum
            birth_count_df[i] = df[df['Event_Name'] == "Births"][["Node_ID", "Event_Name"]].replace(
                {'Event_Name': 'Births'}, {'Event_Name': 1}).groupby("Node_ID").sum()
            # Get death count for each sim. Death count is total NonDiseaseDeaths row count by Node_ID
            death_count_df[i] = df[df['Event_Name'] == "NonDiseaseDeaths"][["Node_ID", "Event_Name"]].replace(
                {'Event_Name': 'NonDiseaseDeaths'}, {'Event_Name': 1}).groupby("Node_ID").sum()

        # birth_count_df is for total simulation duration, in this test, total_sim_year=10, so we need to divide it to
        # get birth_count per year.
        # Since our initial population is 10000, we want to get birth_rate for every 1000 population,
        # so we need to divide birth_count by another 10(i.e second 10 in following statement)
        # we also need to divide by sim_sample_rate since we only got 10 percent of data which defined in sim_sample_rate = 0.1
        actual_birth_rate = birth_count_df.mean(axis=1) / self.total_sim_year / 10 / self.n_replica/self.sim_sample_rate
        actual_death_rate = death_count_df.mean(axis=1) / self.total_sim_year / 10 / self.n_replica/self.sim_sample_rate

        # Get world bank birth rate
        expected_birth_rate = self.wb_births_df[self.wb_births_df['Country Name'] == self.place][str(self.year)].tolist()[0]
        # verify actual_birth_rate is about the same as expected birth_rate which got from worldbank, allow delta diff
        self.assertAlmostEqual(actual_birth_rate.mean(), expected_birth_rate, delta=2)
        # assume expected death_rate = expected birth_rate
        self.assertAlmostEqual(actual_death_rate.mean(), expected_birth_rate, delta=2)

        # ---------------------------------------------
        # Test age distribution
        # We are listening HappyBirthday event, since each person will have birthday in a year, so we can get  all person's
        # age in a year. We use age for calculate age distribution over time and compare with demographics age distribution
        f = open(os.path.join(os.getcwd(), "demographics_vita.json"))
        demog_data = json.load(f)
        f.close()
        # Save age_distribution info to age_dist from demographics.json
        #for i in range(len(demog_data['Nodes'])):
        age_dist = demog_data['Defaults']['IndividualAttributes']['AgeDistribution']
        for sim_reporter in reporteventrecorder_downloaded:
            df = pd.read_csv(sim_reporter)  # read ReportEventRecorder.csv from each sim to dateframe
            # Select only rows with 'HappyBirthday' which contains Age info in the row. then groupby Node_ID
            df_by_node = df[df['Event_Name'] == "HappyBirthday"].groupby("Node_ID")
            age_bin_per_sim_per_node = {}
            # For each node_id
            for node_id, happy_birthday_df in df_by_node:
                # Convert Age from default day value to year and cast to integer
                happy_birthday_df['Age'] = (happy_birthday_df['Age'] / 365).astype(int)
                # Convert Age > 90 to 90 to avoid incorrect assign bin bucket
                #happy_birthday_df.loc[happy_birthday_df["Age"] > 90]['Age'] = 90
                happy_birthday_df.loc[happy_birthday_df["Age"] > 90, 'Age'] = 90
                # Convert happy_birthday_df['Age"] column to demographics.json's age bins and add to 'bins' columns
                # i.e if Age = 71, it will assign to (70. 75] bucket
                happy_birthday_df['bins'] = pd.cut(x=happy_birthday_df['Age'], bins=age_dist['ResultValues'])
                # Get total count for each age bin
                happy_birthday_bin_df = happy_birthday_df[['Event_Name', "bins"]].replace(
                    {"Event_Name": "HappyBirthday"},
                    {"Event_Name": 1}).groupby("bins", observed=False).sum()
                # Rename Event_Name column to proper name 'count'
                happy_birthday_bin_df.rename(columns={'Event_Name': 'count'}, inplace=True)
                age_percent_list = []
                for index, row in happy_birthday_bin_df.iterrows():
                    # Get percentage for each bucket
                    age_percent_list.append(row['count'] / sum(happy_birthday_bin_df['count']))
                happy_birthday_bin_df['percent'] = age_percent_list
                # Get cumulated percentage for each bucket
                happy_birthday_bin_df['cum_percent'] = happy_birthday_bin_df['percent'].cumsum()
                real_age_distribution_cum_percent_values = happy_birthday_bin_df['cum_percent'].tolist()

                # Verify each age bin from each node and each sim will have correct distribution comparing with
                # demographics.json's age distribution
                for age_bucket in range(len(real_age_distribution_cum_percent_values)):

                    expected_age_distribution_at_bucket = age_dist['DistributionValues'][1:][age_bucket]
                    # Verify they are almost the same with 0.02 tolerant
                    # for example in demographics.json, 0.97548758 for age bin (85, 90], the real one maybe 0.985487
                    # for same age bin, we consider this is good enough value
                    self.assertAlmostEqual(expected_age_distribution_at_bucket,
                                           real_age_distribution_cum_percent_values[age_bucket], delta=0.05)