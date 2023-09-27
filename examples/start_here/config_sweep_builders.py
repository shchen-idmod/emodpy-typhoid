import itertools
import params
from typing import List
from functools import partial
from idmtools.builders import SimulationBuilder
from idmtools.entities.simulation import Simulation

from emodpy_typhoid.utility.sweeping import ItvFn, CfgFn, set_param



platform = None


def update_typhoid_configs(config, values):
    config.parameters.Typhoid_Symptomatic_Fraction = values[0]
    config.parameters.Typhoid_Environmental_Exposure_Rate = values[1]
    config.parameters.Typhoid_Contact_Exposure_Rate = values[2]
    return dict(Typhoid_Symptomatic_Fraction=values[0], Typhoid_Environmental_Exposure_Rate=values[1],
                Typhoid_Contact_Exposure_Rate=values[2])


def add_typhoid_vaccine(campaign, values):
    import emodpy_typhoid.interventions.typhoid_vaccine as tv
    event = tv.new_scheduled_intervention(campaign, efficacy=values[0], decay_constant=values[1], start_day=200,
                                          coverage=0.85, node_ids=None, property_restrictions_list=[],
                                          co_event="Vaccinated")
    event_list = []
    event_list.append(event)
    campaign.add( event )
    return {"efficacy": values[0], 'decay_constant': values[1]}


def sweep_simulations(simulation: Simulation, func_list: List):
    """
    Sweeping on simulation.
    Args:
        simulation: idmtools Simulation
        func_list: a list of functions

    Returns:
        dict of parameters
    """
    tags_updated = {}
    for func in func_list:
        tags = func(simulation)
        tags_updated.update(tags)
    return tags_updated


###################################
# Common interface
###################################
def get_sweep_builders(**kwargs):
    """
    Build simulation builders.
    Args:
        kwargs: User inputs may overwrite the entries in the block.

    Returns:
        lis of Simulation builders
    """
    global platform
    platform = kwargs.get('platform', None)
    builder = SimulationBuilder()

    # Test
    if params.test_run:
        builder.add_sweep_definition(partial(set_param, param='Run_Number'), range(params.num_seeds))
        return [builder]


    typhoid_sweep_configs = list(itertools.product(params.typhoid_symptomatic_fraction, params.typhoid_environmental_exposure_rate,
                                          params.typhoid_contact_exposure_rate))

    changing_effect = list(itertools.product(params.initial_effect, params.decay_time_constant))

    funcs_list = [[CfgFn(update_typhoid_configs, c),
                   ItvFn(add_typhoid_vaccine, ce),
                   partial(set_param, param='Run_Number', value=x),
                   ]
                  for c in typhoid_sweep_configs
                  for ce in changing_effect
                  for x in range(params.num_seeds)
                  ]

    builder.add_sweep_definition(sweep_simulations, funcs_list)

    return [builder]
