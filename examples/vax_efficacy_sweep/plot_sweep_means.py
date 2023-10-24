import matplotlib
matplotlib.use("TkAgg")
import emod_api.channelreports.plot_icj_means as plotter
exp_id = "latest_experiment"
#chan = "New Infections By Route (CONTACT)"
#chan = "New Infections By Route (CONTACT)_CUMULATIVE"
chan = "New Infections By Route (ENVIRONMENT)_CUMULATIVE"
chan_data = plotter.collect(exp_id, chan, tag="efficacy=SWEEP")
plotter.display(chan_data, False, chan, exp_id)

