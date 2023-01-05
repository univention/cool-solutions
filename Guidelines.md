
# Guidelines for Cool Solutions

## Packaging & structure
* add a `README.md` to the root of your package folder, add this file to `debian/<packagename>.docs`
* if you add schema extensions: provide a way to properly disable them on package deinstallation (e.g. `.postrm` or `.uinst`)
* If possible, make your package compatible to UCS4 and 5. If not, test the update procedure.

## Documentation
* Add technical information to the `README.md`
* Link to the according article at [help.univention.de](https://help.univention.com/c/knowledge-base/cool-solutions/51) (if not, write one)

## Code guidelines

Taken from <https://univention.gitpages.knut.univention.de/internal/dev-onboarding/code-guidelines.html>

### Python

* PEP8 compatible

> 7.2.1. PEP 8 coding style and annotations
>
>     Source code file encoding must be UTF-8. In Python files, define it with the line # -*- coding: utf-8 -*-.
>
> PEP 8 exceptions
>
> The difference with PEP 8 consists of the following exceptions:
>
>     No additional indentation with single spaces in a new line.
>
>     No limitation of the line length. Adding a line-break at 80 characters often makes code hard to read. Keep the line length below 160 characters wide. For the exception in UCS@school, see UCS@school.
>
> This results in the exceptions E501, W191, E265, C901, and W503 described in pycodestyle - Error codes and flake8 - Error / Violation Codes. For configuration of these tools, refer to Automatic tools.
>
> E501 (^)             line too long (82 > 79 characters)
> W191                 indentation contains tabs
> E265                 block comment should start with '# '
> C901                 maximum mccabe complexity higher than 10
> W503                 line break occurred before a binary operator


### Bash

Use [shellcheck](https://www.shellcheck.net/) to lint your bash scripts.

Don’t use backticks. Instead use for example `$(date)`.

Use quoting, especially for the following:

```bash
"$@"
eval "$(univention-config-registry shell)"
eval "$(univention_policy_result -s "$(univention-config-registry get ldap/hostdn)")"
```

* Maybe it’s better to use Python directly.
* Use natural line breaks instead of \, for example after |, ||, &&.

```bash
# Recommend
today="$(date +%Y%m%d)"
eval "$(ucr shell)"
dmesg |
  grep -q 'ERROR:' ||
  echo 'Alles okay'

# Not recommended
today=`date`
eval ucr shell
dmesg \
  | grep ERROR: >/dev/null \
  || echo Alles okay
```


### Debian

* Comply `debian/changelog` to a [DEP-5 machine readable file](https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/).
* Sort and wrap `debian/control` with `wrap-and-sort -ast`.
* Prefix all debhelper files `debian/$pkg.$dh` with the binary package name.
* List only directories in and explicitly create `debian/$pkg.dirs`. Don’t name directories implicitly created by other debhelper scripts like dh_install. Follow the principle convention over configuration.

