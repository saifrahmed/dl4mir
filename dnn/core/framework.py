"""
"""


from ejhumphrey.dnn.core.layers import Layer
from ejhumphrey.dnn.core.graphs import Network
from ejhumphrey.dnn.core.modules import Loss
from ejhumphrey.dnn.core.updates import SGD

import json
import os
import time

def select_update(base, newdict):
    """Update a dictionary with only the intersection of the two key sets."""
    for k, v in newdict.iteritems():
        if k in base:
            base[k] = v

def json_save(obj, filename):
    """Serialize a network to disk.

    Parameters
    ----------
    net : Network
        Instantiated network to serialize.
    filebase : string
        Path to write the appropriate information. Two time-stamped files are
        created:
        1. A human-readable json dump of the network architecture.
        2. A pickled dictionary of the networks numerical parameters.
    """
    base_directory = os.path.split(filename)[0]
    if not os.path.exists(base_directory):
        os.makedirs(base_directory)

    # Save json-encoded architecture.
    file_handle = open(filename, "w")
    json.dump(obj, file_handle, indent=2)
    file_handle.close()

class Trainer(object):

    def __init__(self, name, save_directory):
        self.network = None
        self.loss = None
        self.update = None
        self.monitor = None
        self.input_name, self.output_name = "input", "output"
        self.target_name = "y_target"
        self.name = name
        self.save_directory = os.path.join(save_directory, self.name)
        if not os.path.exists(self.save_directory):
            os.makedirs(self.save_directory)
        self.save_filebase = os.path.join(self.save_directory, self.name)
        self.stats_handle = open("%s-stats.txt" % self.save_filebase, 'w')


    def build_network(self, layer_args):
        """
        Parameters
        ----------
        layer_args : list of arg-like dicts
            Can be created with an argument factory or loaded from a json-file.
        """
        self.network = Network([Layer(args) for args in layer_args])
        self.network.compile(self.input_name, self.output_name)
        self.network.save_definition(self.save_filebase, False)

    def configure_losses(self, loss_args):
        """
        Parameters
        ----------
        loss_args : list of tuples
            Each tuple must contain a string pointing to a representation in
            network.vars and a loss type declared in LossFunctions.
        """
        assert self.network, "Network must be built first."
        self.loss = Loss()
        for iname, ltype in loss_args:
            self.loss.register(self.network, iname, ltype)
        self.loss.compile()
        json_save(loss_args, "%s-loss_args.txt" % self.save_filebase)

    def configure_updates(self, update_args=None):
        """
        Parameters
        ----------
        update_args : list of strings, default None
            Names of parameters in the network to update.
        """
        assert self.loss, "Loss must be configured first."
        self.update = SGD()
        if update_args is None:
            update_args = self.network.params.keys()
        params = dict([(k, self.network.params.get(k)) for k in update_args])
        self.update.compute_updates(self.loss, params)
        self.update.compile()
        json_save(update_args, "%s-update_args.txt" % self.save_filebase)


    def run(self, sources, train_params, hyperparams):
        assert self.network, "Network must be built first."
        assert self.loss, "Loss must be configured first."
        assert self.update, "Update must be configured first."
        print "[%s]\t Running ..." % time.asctime()

        Done = False
        train_inputs = self.update.empty_inputs()
        select_update(train_inputs, hyperparams)

        loss_inputs = self.loss.empty_inputs()
        select_update(loss_inputs, hyperparams)
        json_save(hyperparams, "%s-hyperparams.txt" % self.save_filebase)
        json_save(train_params, "%s-train_params.txt" % self.save_filebase)
        while not Done:
            try:
                batch = sources['train'].next_batch(train_params.get("batch_size"))
                train_inputs[self.input_name] = batch.values
                train_inputs[self.target_name] = batch.labels

                train_loss = self.update(train_inputs)

                if (self.update.iteration % train_params["checkpoint_freq"]) == 0:
                    self.checkpoint(train_loss)

                if self.update.iteration >= train_params.get("max_iterations"):
                    Done = True

            except KeyboardInterrupt:
                break
        print "\nFinished.\n"

    def checkpoint(self, train_loss):
        self.network.save_params("%s_%07d" % (self.save_filebase,
                                              self.update.iteration),
                                 True)
        stat_line = "[%s]\t iter: %07d \ttrain loss: %0.4f" % \
            (time.asctime(), self.update.iteration, train_loss)
        self.stats_handle.write(stat_line + "\n")
        print stat_line

    def __del__(self):
        self.stats_handle.close()
