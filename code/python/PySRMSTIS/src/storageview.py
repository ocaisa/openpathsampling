import sys
import argparse
from Simulator import Simulator
from ensemble import LengthEnsemble, InXEnsemble, OutXEnsemble
from trajectory import Trajectory
from snapshot import Snapshot
from storage import Storage
import os

if __name__ == '__main__':


    parser = argparse.ArgumentParser(description='Analyze a file.')
    parser.add_argument('file', metavar='file.nc', help='an integer for the accumulator')

    args = parser.parse_args()
    file = args.file

    if not os.path.isfile(file):
        print file, 'does not exist ! ENDING!'
        exit()

    storage = Storage(
                                                     filename = file,
                                                     mode = 'a'
                                                     )

    def headline(s):
        print
        print "###################################################################################"
        print "##", s.upper()
        print "###################################################################################"
        print

    def line(a, b):
        print '    {:<32} : {:<30}'.format(a,b)

    def nline(n, a, b):
        print '    [{:<4}] {:<25} : {:<30}'.format(n,a,b)


    headline("General")

    line("Filename", file)
    line("Size", str(os.path.getsize(file) / 1024 / 1024) + " MB")

    headline("Content")

    line("Number of trajectories", storage.trajectory.count())
    line("Number of configurations", storage.configuration.count())
    line("Number of momenta", storage.momentum.count())

    headline("Topology")

    topology = storage.topology

    line("Number of Atoms", topology.n_atoms)

    counterion_indices = [ a.index for a in topology.atoms if a.residue.name[-1] == '+']
    solvent_indices = [ a.index for a in topology.atoms if a.residue.name == 'HOH']
    protein_indices = [ a.index for a in topology.atoms if a.residue.name[-1] != '+' and a.residue.name != 'HOH']

    line("Number of waters", len(solvent_indices) / 3)
    line("Number of protein atoms", len(protein_indices))

    headline("Shapshot Zero")
    # load initial equilibrate snapshot given by ID #0
    snapshot = storage.snapshot.load(0, 0)

    line("Potential Energy",snapshot.potential_energy)
    line("Kinetic Energy",snapshot.kinetic_energy)

    headline("Ensembles")

    for e_idx in range(1, storage.ensemble.count() + 1):
        ensemble = storage.ensemble.load(e_idx)
        nline(e_idx,ensemble.name,ensemble.description.replace('\n', ''))

    headline("Origins")

    for o_idx in range(1, storage.origin.count() + 1):
        origin = storage.origin.load(o_idx)
        nline(o_idx, origin.name, str([t.idx[storage] for t in origin.inputs]) +" -> " + str(origin.final.idx[storage]) + " in " + origin.ensemble.name + " [" + str(origin.ensemble.idx[storage]) + "]")

    headline("Trajectories")

    for t_idx in range(1, storage.trajectory.count() + 1):
        traj = storage.trajectory.configuration_indices(t_idx)
        sys.stdout.write("  {:>4} [{:>5} frames] : ".format(str(t_idx),str(len(traj))))
        old_idx = -2
        count = 0
        for idx in traj:
            if idx == old_idx + 1 or idx == old_idx - 1:
                count += 1
            else:
                if count > 1:
                    sys.stdout.write(" <" + str(count - 1) + ">")
                if old_idx >= 0 and count > 0:
                    sys.stdout.write(" " + str(old_idx))
                sys.stdout.write(" " + str(idx))
                count = 0
            old_idx = idx

        if count > 1:
            sys.stdout.write(" ... <" + str(count - 1) + "> ...")
        if count > 0:
            sys.stdout.write(" " + str(old_idx))


        sys.stdout.write("\n")


