from emod_api import schema_to_class as s2c


def new_intervention( camp, multuplier_by_duration ):
    intervention = s2c.get_class_with_defaults("NodeInfectivityMult", camp.schema_path)
    intervention.Multiplier_By_Duration.Times = multuplier_by_duration['Times']
    intervention.Multiplier_By_Duration.Values = multuplier_by_duration['Values']
    intervention.Transmission_Route = "ENVIRONMENTAL"
    return intervention

