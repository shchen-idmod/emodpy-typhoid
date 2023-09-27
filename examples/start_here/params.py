import os
import pandas as pd
import manifest

# run test
test_run = False

# parameters
typhoid_symptomatic_fraction = [0.06470627473749248, 0.057664943255278454]
typhoid_environmental_exposure_rate = [0.532891163188627]
typhoid_contact_exposure_rate = [1.0]

exp_name = "Typhoid Hello World"
decay_time_constant = [50, 100]
initial_effect = [0.82, 0.95]
num_seeds = 2
base_year=1917
