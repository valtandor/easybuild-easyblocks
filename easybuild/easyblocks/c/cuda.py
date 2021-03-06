##
# This file is an EasyBuild reciPY as per https://github.com/hpcugent/easybuild
#
# Copyright:: Copyright 2012-2015 Cyprus Institute / CaSToRC, Uni.Lu, NTUA, Ghent University
# Authors::   George Tsouloupas <g.tsouloupas@cyi.ac.cy>, Fotis Georgatos <fotis@cern.ch>, Kenneth Hoste
# License::   MIT/GPL
# $Id$
#
# This work implements a part of the HPCBIOS project and is a component of the policy:
# http://hpcbios.readthedocs.org/en/latest/HPCBIOS_2012-99.html
##
"""
EasyBuild support for CUDA, implemented as an easyblock

Ref: https://speakerdeck.com/ajdecon/introduction-to-the-cuda-toolkit-for-building-applications

@author: George Tsouloupas (Cyprus Institute)
@author: Fotis Georgatos (Uni.lu)
@author: Kenneth Hoste (Ghent University)
"""
import os
from distutils.version import LooseVersion

from easybuild.easyblocks.generic.binary import Binary
from easybuild.tools.filetools import patch_perl_script_autoflush
from easybuild.tools.run import run_cmd, run_cmd_qa
from easybuild.tools.systemtools import get_shared_lib_ext


class EB_CUDA(Binary):
    """
    Support for installing CUDA.
    """

    def extract_step(self):
        """Extract installer to have more control, e.g. options, patching Perl scripts, etc."""
        execpath = self.src[0]['path']
        run_cmd("/bin/sh " + execpath + " --noexec --nox11 --target " + self.builddir)
        self.src[0]['finalpath'] = self.builddir

    def install_step(self):
        """Install CUDA using Perl install script."""

        # define how to run the installer
        # script has /usr/bin/perl hardcoded, but we want to have control over which perl is being used
        if LooseVersion(self.version) <= LooseVersion("5"):
            install_script = "install-linux.pl"
            install_script_path = os.path.join(self.builddir, install_script)
            cmd = "perl ./%s --prefix=%s %s" % (install_script, self.installdir, self.cfg['installopts'])
        else:
            # the following would require to include "osdependencies = 'libglut'" because of samples
            # installparams = "-samplespath=%(x)s/samples/ -toolkitpath=%(x)s -samples -toolkit" % {'x': self.installdir}
            install_script = "cuda-installer.pl"
            installparams = "-toolkitpath=%s -toolkit" % self.installdir
            cmd = "perl ./%s -verbose -silent %s %s" % (install_script, installparams, self.cfg['installopts'])

        # prepare for running install script autonomously
        qanda = {}
        stdqa = {
            # this question is only asked if CUDA tools are already available system-wide
            r"Would you like to remove all CUDA files under .*? (yes/no/abort): ": "no",
        }
        noqanda = [
            r"^Configuring",
            r"Installation Complete",
            r"Verifying archive integrity.*",
            r"^Uncompressing NVIDIA CUDA",
            r".* -> .*",
        ]

        # patch install script to handle Q&A autonomously
        patch_perl_script_autoflush(os.path.join(self.builddir, install_script))

        # make sure $DISPLAY is not defined, which may lead to (weird) problems
        # this is workaround for not being able to specify --nox11 to the Perl install scripts
        if 'DISPLAY' in os.environ:
            os.environ.pop('DISPLAY')
    
        #overriding maxhits default value to 300 (300s wait for nothing to change in the output without seeing a known question)
        run_cmd_qa(cmd, qanda, std_qa=stdqa, no_qa=noqanda, log_all=True, simple=True, maxhits=300)

    def sanity_check_step(self):
        """Custom sanity check for CUDA."""
        shlib_ext = get_shared_lib_ext()

        chk_libdir = ["lib64"]
        
        # Versions higher than 6 do not provide 32 bit libraries
        if LooseVersion(self.version) < LooseVersion("6"):
            chk_libdir += ["lib"]

        extra_files = []
        if LooseVersion(self.version) < LooseVersion('7'):
            extra_files.append('open64/bin/nvopencc')

        custom_paths = {
            'files': ["bin/%s" % x for x in ["fatbinary", "nvcc", "nvlink", "ptxas"]] + extra_files +
                     ["%s/lib%s.%s" % (x, y, shlib_ext) for x in chk_libdir for y in ["cublas", "cudart", "cufft",
                                                                                      "curand", "cusparse"]],
            'dirs': ["include"],
        }

        super(EB_CUDA, self).sanity_check_step(custom_paths=custom_paths)

    def make_module_req_guess(self):
        """Specify CUDA custom values for PATH etc."""

        guesses = super(EB_CUDA, self).make_module_req_guess()

        guesses.update({
            'PATH': ['open64/bin', 'bin'],
            'LD_LIBRARY_PATH': ['lib64'],
            'CPATH': ['include'],
            'CUDA_HOME': [''],
            'CUDA_PATH': [''],
        })

        return guesses
