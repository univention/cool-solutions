**Note:** Cool Solutions are articles documenting additional functionality based on Univention products. Packages provided by a Cool Solutions Repository are built by Univention professional service, but will not necessarily be maintained. Not all the shown steps in the article are covered by Univention Support. For questions about your support coverage, contact your contact person at Univention before you want to implement one of the shown steps.

Further documentation & discussion at: <https://help.univention.com/t/cool-solutions-articles-and-repository/11517>

# Introduction

Cool Solutions are articles documenting additional functionality based on Univention products. Packages provided by a Cool Solutions Repository are built by Univention, but will not be maintained.
Not all of the shown steps in the article are covered by Univention Support. For questions about your support coverage contact your contact person at Univention before you want to implement one of the shown steps.

# Repository integration

Some solutions need special packages build by Univention. These packages are provided in a Cool Solutions Repository. There are different possibilities to integrate the Cool Solutions Repository.

In the Univention Management Console, Software tab, open the module *Repository settings* and add a new repository component with Component Name *cool-solutions* and Advanced Setting *Use unmaintained repositories*.

Alternatively, set the following Univention Configuration Registry variables on the console:

```
ucr set \
  repository/online/component/cool-solutions=yes \
  repository/online/component/cool-solutions/version=current \
  repository/online/component/cool-solutions/unmaintained=yes
```

# Upgrade

If you have a cool solution repository integrated and plan to upgrade, please check if the Cool Solution is already available for your target UCS Version.

# Source Code

All Cool Solutions packages and their source code can be found at our [github mirror](https://github.com/univention/cool-solutions). Feel free to fork the code repository, enhance a package and start a pull request.

