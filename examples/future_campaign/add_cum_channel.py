import numpy as np
import json
import sys
import copy

json_file = sys.argv[1]
existing_channel = sys.argv[2]

with open( json_file ) as icj_fp:
    icj = json.load( icj_fp )
data = icj["Channels"][existing_channel]["Data"]

cum_data = np.cumsum( data )
new_chan = existing_channel+"_CUMULATIVE"

icj["Channels"][new_chan] = copy.deepcopy( icj["Channels"][existing_channel] )
icj["Channels"][new_chan]["Data"] = [ int(x) for x in cum_data]

with open( json_file, "w" ) as icj_fp:
    json.dump( icj, icj_fp ) 
