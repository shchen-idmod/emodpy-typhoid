import unittest
import emodpy_typhoid.interventions.typhoid_vaccine as ty
import emodpy_typhoid.interventions.typhoid_wash as tw
import emodpy_typhoid.interventions.tcd as tcd
import emodpy_typhoid.interventions.tcc as tcc
import emod_api.campaign as camp

class TestTyphoidInterventions(unittest.TestCase):
    def setUp(self):
        # Initialize campaign and set schema before each test
        import emod_typhoid.bootstrap as dtk
        dtk.setup( "model_files")
        camp.set_schema("model_files/schema.json")

    def test_typhoid_vaccine_intervention(self):
        # Create intervention for typhoid vaccine
        ty.new_intervention_as_file(camp, start_day=4)
        # Assert that the intervention has been created successfully
        # You can add more specific assertions based on the behavior of the intervention

    def test_typhoid_wash_intervention(self):
        # Create intervention for typhoid wash
        tw.new_intervention_as_file(camp, start_day=4)
        # Assert that the intervention has been created successfully
        # You can add more specific assertions based on the behavior of the intervention

    def test_tcc_intervention(self):
        # Create intervention for tcc (typhoid intervention specific to your model)
        tcc.new_intervention_as_file(camp, start_day=4)
        # Assert that the intervention has been created successfully
        # You can add more specific assertions based on the behavior of the intervention

    def test_tcd_intervention(self):
        # Create intervention for tcd (typhoid intervention specific to your model)
        tcd.new_intervention_as_file(camp, start_day=4)
        # Assert that the intervention has been created successfully
        # You can add more specific assertions based on the behavior of the intervention

if __name__ == "__main__":
    unittest.main()

