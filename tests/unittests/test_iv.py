import copy
import json
import os
import pathlib
import unittest
import emodpy_typhoid.interventions.typhoid_vaccine as ty
import emodpy_typhoid.interventions.typhoid_wash as tw
import emodpy_typhoid.interventions.tcd as tcd
import emodpy_typhoid.interventions.tcc as tcc
import emod_api.campaign as camp


def read_camp(filename):
    f = open(os.path.join(os.getcwd(), filename))
    camp_data = json.load(f)
    f.close()
    return camp_data


class TestTyphoidInterventions(unittest.TestCase):

    def parse_intervention(self, camp_data):
        self.event_coordinator = camp_data["Event_Coordinator_Config"]
        self.intervention_config = self.event_coordinator["Intervention_Config"]

    def setUp(self):
        # Initialize campaign and set schema before each test
        import emod_typhoid.bootstrap as dtk
        dtk.setup("model_files")
        camp.set_schema("model_files/schema.json")
        self.case_name = self._testMethodName
        self.camp = camp

    def tearDown(self) -> None:
        file_to_rem = pathlib.Path(self.case_name)
        file_to_rem.unlink(missing_ok=True)
        self.camp = None

    def test_typhoid_vaccine_intervention(self):
        # Create intervention for typhoid vaccine
        start_day = 4
        ty.new_intervention_as_file(camp=self.camp, start_day=start_day, filename=self.case_name)
        camp_data = read_camp(self.case_name)
        self.parse_intervention(camp_data['Events'][0])
        self.assertEqual(
            self.event_coordinator['Intervention_Config']['Actual_IndividualIntervention_Config']['Intervention_Name'],
            'TyphoidVaccine')
        self.assertEqual(self.event_coordinator['Intervention_Config']['Actual_IndividualIntervention_Config']['class'],
                         'TyphoidVaccine')
        self.assertEqual(camp_data['Events'][0]['Start_Day'], float(start_day))
        self.assertListEqual(self.intervention_config['Trigger_Condition_List'], ['Births'])
        self.assertEqual(self.intervention_config['class'], 'NodeLevelHealthTriggeredIV')

    def test_tcc_intervention(self):
        # Create intervention for tcc (typhoid intervention specific to your model)
        start_day = 4
        tcc.new_intervention_as_file(camp=self.camp, start_day=start_day, filename=self.case_name)
        camp_data = read_camp(self.case_name)
        self.parse_intervention(camp_data['Events'][0])
        self.assertEqual(
            self.event_coordinator['Intervention_Config']['Intervention_Name'], 'NodeLevelHealthTriggeredIV')
        self.assertEqual(self.event_coordinator['Intervention_Config']['Actual_IndividualIntervention_Config']['class'],
                         'TyphoidCarrierClear')
        self.assertEqual(
            self.event_coordinator['Intervention_Config']['Actual_IndividualIntervention_Config']['Clearance_Rate'],
            0.567)
        self.assertEqual(camp_data['Events'][0]['Start_Day'], float(start_day))
        self.assertListEqual(self.event_coordinator['Intervention_Config']['Trigger_Condition_List'], ['Births'])
        self.assertEqual(self.event_coordinator['Intervention_Config']['class'], 'NodeLevelHealthTriggeredIV')

    def test_tcd_intervention(self):
        # Create intervention for tcd (typhoid intervention specific to your model)
        start_day = 4
        tcd.new_intervention_as_file(camp=self.camp, start_day=start_day, filename=self.case_name)
        camp_data = read_camp(self.case_name)
        self.parse_intervention(camp_data['Events'][0])
        self.assertEqual(
            self.event_coordinator['Intervention_Config']['Intervention_Name'], 'NodeLevelHealthTriggeredIV')
        self.assertEqual(self.intervention_config['Actual_IndividualIntervention_Config']['Intervention_Name'],
                         'TyphoidCarrierDiagnostic')
        self.assertEqual(
            self.intervention_config['Actual_IndividualIntervention_Config']['Positive_Diagnosis_Event'],
            'TestedPositive')
        self.assertEqual(camp_data['Events'][0]['Start_Day'], float(start_day))
        self.assertListEqual(self.event_coordinator['Intervention_Config']['Trigger_Condition_List'], ['Births'])
        self.assertEqual(self.event_coordinator['Intervention_Config']['class'], 'NodeLevelHealthTriggeredIV')

    def test_scheduled_typhoid_vaccine_intervention(self):
        start_day = 4
        cov = 0.7
        decay_constant = 1234
        efficacy = 0.8
        property_restrictions_list = ['Demo:1']
        expected_property_restrictions_list = copy.deepcopy(property_restrictions_list)
        event = ty.new_scheduled_intervention(camp=self.camp, start_day=start_day, coverage=cov, efficacy=efficacy,
                                              decay_constant=decay_constant,
                                              property_restrictions_list=property_restrictions_list)
        self.parse_intervention(event)
        self.assertEqual(event['Start_Day'], float(start_day))
        self.assertEqual(self.intervention_config['Intervention_Name'], 'TyphoidVaccine')
        self.assertEqual(self.intervention_config['Changing_Effect']['class'],
                         'WaningEffectBoxExponential')
        self.assertEqual(self.intervention_config['Changing_Effect']['Decay_Time_Constant'], float(decay_constant))
        self.assertEqual(self.intervention_config['Changing_Effect']['Initial_Effect'], float(efficacy))
        self.assertEqual(self.intervention_config['Effect'], float(efficacy))
        self.assertEqual(self.intervention_config['Mode'], 'Shedding')
        self.assertListEqual(self.event_coordinator['Property_Restrictions'], expected_property_restrictions_list)

    # comment out this test since there is no TyphoidWASH in schema
    # def test_typhoid_wash_intervention(self):
    #     # Create intervention for typhoid wash
    #     start_day = 4
    #     tw.new_intervention_as_file(camp, start_day=start_day, filename=self.case_name)
    #     camp_data = self.read_camp(self.case_name)
    #     self.parse_intervention(camp_data['Events'][0])


if __name__ == "__main__":
    unittest.main()
