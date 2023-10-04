def cleanup_for_2018_mode( config ):
    # when using 2018 binary
    config.parameters.pop( "Serialized_Population_Filenames" )
    config.parameters.pop( "Serialization_Time_Steps" )
    config.parameters.pop( "Demographics_Filename" )

    config.parameters.Incubation_Period_Distribution = "FIXED_DURATION" # hack
    config.parameters.Infectious_Period_Distribution = "FIXED_DURATION" # hack
    config.parameters.Base_Incubation_Period = 1
    config.parameters.Base_Infectious_Period = 1

