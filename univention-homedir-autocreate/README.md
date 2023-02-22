# Univention Homdedir Autocreate

## Introduction

The package univention-homedir-autocreate creates a users home directory automatically without the need of a login from the user. However, this packages does not create home directories on a NFS share. This is done by the listener module nfs-homes which comes with the package univention-nfs.

## Installation

After enabling the Cool Solutions Repository you can install the package with the following command:

univention-install univention-homedir-autocreate

## Usage

By setting the Unix Home Directory in the Account tab of the UMC, the listener gets triggered and creates the respective directory. Additional folders can be created using univention-skel upon the first login of the user.