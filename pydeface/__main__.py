#!/usr/bin/env python
"""Defacing utility for MRI images."""

# Copyright 2011, Russell Poldrack. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY RUSSELL POLDRACK ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL RUSSELL POLDRACK OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import os
import tempfile
import numpy as np
from nipype.interfaces import fsl
from nibabel import load, Nifti1Image
from pkg_resources import require
from pydeface.utils import initial_checks, output_checks


def deface_image(args):
    """Warp the facemask in template space to that of infile
    and return the warped mask that was applied."""
    template, facemask = initial_checks(args.template, args.facemask)
    infile = args.infile
    outfile = output_checks(infile, args.outfile, args.force)

    # temporary files
    _, template_reg_mat = tempfile.mkstemp()
    template_reg_mat = template_reg_mat + '.mat'
    _, warped_mask = tempfile.mkstemp()
    warped_mask = warped_mask + '.nii.gz'
    if args.verbose:
        print("Temporary files:\n  %s\n  %s" % (template_reg_mat, warped_mask))
    _, template_reg = tempfile.mkstemp()
    _, warped_mask_mat = tempfile.mkstemp()

    print('Defacing...\n  %s' % infile)

    # register template to infile
    flirt = fsl.FLIRT()
    flirt.inputs.cost_func = args.cost
    flirt.inputs.in_file = template
    flirt.inputs.out_matrix_file = template_reg_mat
    flirt.inputs.out_file = template_reg
    flirt.inputs.reference = infile
    flirt.run()

    # warp facemask to infile
    flirt = fsl.FLIRT()
    flirt.inputs.in_file = facemask
    flirt.inputs.in_matrix_file = template_reg_mat
    flirt.inputs.apply_xfm = True
    flirt.inputs.reference = infile
    flirt.inputs.out_file = warped_mask
    flirt.inputs.out_matrix_file = warped_mask_mat
    flirt.run()

    # multiply mask by infile and save
    infile_img = load(infile)
    warped_mask_img = load(warped_mask)
    try:
        outdata = infile_img.get_data().squeeze() * warped_mask_img.get_data()
    except ValueError:
        tmpdata = np.stack(
            [warped_mask_img.get_data()] *
            infile_img.get_data().
            shape[-1], axis=-1)
        outdata = infile_img.get_data() * tmpdata

    masked_brain = Nifti1Image(outdata, infile_img.get_affine(),
                               infile_img.get_header())
    masked_brain.to_filename(outfile)

    if args.nocleanup:
        pass
    else:
        os.remove(warped_mask)
        os.remove(template_reg)
        os.remove(template_reg_mat)

    print("Defaced image saved as:\n  %s" % outfile)
    return warped_mask_img


def main():
    """Command line call argument parsing."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infile', metavar='path',
        help="Path to input nifti.")

    parser.add_argument(
        "--outfile", metavar='path', required=False,
        help="If not provided adds '_defaced' suffix.")

    parser.add_argument(
        "--force", action='store_true',
        help="Force to rewrite the output even if it exists.")

    parser.add_argument(
        '--applyto', nargs='+', required=False, metavar='',
        help="Apply the created face mask to other images. Can take multiple "
             "arguments.")

    parser.add_argument(
        "--cost", metavar='mutualinfo', required=False, default='mutualinfo',
        help="FSL-FLIRT cost function. Default is 'mutualinfo'.")

    parser.add_argument(
        "--template", metavar='path', required=False,
        help=("Optional template image that will be used as the registration "
              "target instead of the default."))

    parser.add_argument(
        "--facemask", metavar='path', required=False,
        help="Optional face mask image that will be used instead of the "
             "default.")

    parser.add_argument(
        "--nocleanup", action='store_true',
        help="Do not cleanup temporary files. Off by default.")

    parser.add_argument(
        "--verbose", action='store_true',
        help="Show additional status prints. Off by default.")

    welcome_str = 'pydeface ' + require("pydeface")[0].version
    welcome_decor = '-' * len(welcome_str)
    print(welcome_decor + '\n' + welcome_str + '\n' + welcome_decor)

    args = parser.parse_args()

    warped_mask_img = deface_image(args)

    # apply mask to other given images
    if args.applyto is not None:
        print("Defacing mask also applied to:")
        for applyfile in args.applyto:
            applyfile_img = load(applyfile)
            outdata = applyfile_img.get_data() * warped_mask_img.get_data()
            applyfile_img = Nifti1Image(outdata, applyfile_img.get_affine(),
                                        applyfile_img.get_header())
            outfile = output_checks(applyfile)
            applyfile_img.to_filename(outfile)
            print('  %s' % applyfile)

    print('Finished.')


if __name__ == "__main__":
    main()
