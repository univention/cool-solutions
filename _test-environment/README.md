# Test Environments (TDP / Proxmox)

This directory holds everything needed to spin up per-package test environments
in CI: Proxmox VMs, Aptly repo setup, and the Ansible playbooks that install
and exercise each package. It's driven entirely from `.gitlab-ci.yml` via the
[test-dev-pipeline (TDP)](https://git.knut.univention.de/univention/prof-services/internal/devops/test-dev-pipeline)
`jobs-library.yml` include (see the `TDP_VERSION` pin at the top of
`.gitlab-ci.yml`).

## Directory layout

| Path | Purpose |
|---|---|
| `configs/*.cfg` | TDP "environment config" files (one section per VM role: `pdn`, `bdn1`, `member-nextcloud`, ...). Defines the Proxmox template to clone, per-VM setup commands, and files to push. One cfg per package group, shared across UCS versions where the group doesn't need per-version variants (e.g. `sudo-ldap-ucs52.cfg`), and per-flavor where it does (e.g. `nextcloud-schema-config.cfg` vs `nextcloud-schema-config-ucs52.cfg`). |
| `ansible/playbook-<pkg>.yml` | Installs the package(s) from the MR's Aptly repo onto the already-provisioned VM(s). |
| `ansible/playbook-<pkg>-test.yml` | Runs against the same VM(s) after install to verify the package actually works (see [Smoke tests vs. real tests](#smoke-tests-vs-real-tests)). |
| `ansible/playbook-update-packages.yml` | Generic "point this VM at the MR's Aptly repo and refresh installed packages" playbook, used by the shared `configure_aptly` job before the package-specific install playbook runs. |
| `utils/utils.sh` | Shell helpers (`basic_setup`, `basic_setup_ucs_joined`, `add_tech_key_authorized_keys`, `upgrade_to_latest_errata`, `prepare_results`, ...) sourced by cfg `command*` blocks on the VM itself. Pushed to each VM via the cfg's `files:` line. |
| `files/<pkg>/` | Fixtures a package's install/test playbook needs on the VM (installer scripts, demo LDIFs, test data). |

## Job flow per package group

Each package group wires up to five CI jobs (see `create_vms_sudo_ldap` /
`configure_aptly_sudo_ldap` / `run_playbooks_sudo_ldap` / `test_sudo_ldap` /
`terminate_sudo_ldap` in `.gitlab-ci.yml` for the canonical example):

1. **`create_vms_<pkg>`** (`.cs_create_vms` → TDP's `.tdp_create_vms`) — clones the
   Proxmox template(s) named in the group's cfg and runs each section's `command1`
   (basic setup, DNS, join fixups) / `command2` (join, usually a no-op — see
   [Pre-joined templates](#pre-joined-templates)).
2. **`configure_aptly_<pkg>`** (`.cs_configure_aptly` → TDP's `.run_playbooks:after_repo`) —
   points the VM(s) at the MR's Aptly repo via `playbook-update-packages.yml`.
3. **`run_playbooks_<pkg>`** (`.cs_run_playbooks` → TDP's `.tdp_run_playbooks`) —
   runs `ansible/playbook-<pkg>.yml` to install the package(s) under test.
4. **`test_<pkg>`** (same base as step 3, `stage: tests`) — runs
   `ansible/playbook-<pkg>-test.yml` to verify the install.
5. **`terminate_<pkg>`** (`.cs_terminate` → TDP's `.tdp_stop_deployment`) — tears
   the VM(s) down; wired as `on_stop` on `create_vms_<pkg>`'s `environment:` so it
   also fires automatically when the MR/branch environment is stopped.

Each job sets `TDP_ENV_NAME: <pkg>`, which both TDP's Proxmox naming and the
deployment cache key (`${CI_COMMIT_REF_SLUG}-${TDP_ENV_NAME}-deployment`, set in
the `.cs_*` templates) key off of. This scoping is what lets multiple package
groups' VMs live concurrently on the same branch/MR without colliding — don't
drop it when adding a new group.

Jobs only run when their group's files change: each group has a
`.<pkg>_changes: &<PKG>_CHANGES` anchor near the top of `.gitlab-ci.yml` listing
the package directories (plus `_test-environment/**/*`, since a shared-utility
change should re-test everything). `create_vms_<pkg>` / `terminate_<pkg>` are
`when: manual` even when triggered (Proxmox capacity is limited); `configure_aptly_<pkg>` /
`run_playbooks_<pkg>` / `test_<pkg>` run automatically once the VMs exist.

## Pre-joined templates

The Proxmox templates referenced by cfg (`template-ucs-joined-5.2-6-primary`,
`template-ucs-joined-5.2-6-backup`, `template-ucs-joined-5.2-6-replica`,
`template-ucs-joined-5.2-6-member`) are **already joined to a domain** at the image
level — cloning one gives you a VM that's already a DC primary/backup/replica or
member, not a bare UCS install. This replaced the old pattern of joining each
VM from scratch on every pipeline run.

Consequences that show up in every cfg's `command1`/`command2`:

- `command2` (the traditional "join" step) is a no-op — the comment
  `# no join step: template-<role>-joined-5.2-6 is already joined to the domain`
  marks this everywhere it applies.
- `command1` still runs `utils.sh; basic_setup_ucs_joined "<pdn_IP>"` — this is
  **not** a join, it's post-clone identity/network fixup (the clone needs to
  re-register itself with the domain's primary now that it has a new IP/hostname
  from Proxmox), plus `add_tech_key_authorized_keys` and
  `upgrade_to_latest_errata`.
- Set up a new package group's cfg by cloning one of the existing
  `template-*-joined-5.2-6` sections in `generic-5.cfg` rather than writing join
  logic from scratch.

### DNS forwarder

Every joined role except `member` (which has no local BIND) sets
`nameserver1`/`nameserver2`/`dns/forwarder1`/`dns/forwarder2` to the knut
resolvers and restarts `named` in `command1`. A pre-joined VM's DNS still
points at whatever the template baked in; without pointing it at a forwarder
that can resolve the outside world, errata upgrades and Aptly repo access
in later steps fail to resolve. `member` roles skip the forwarder/`named`
restart and just repoint `resolv.conf` directly at knut DNS, since they don't
run their own BIND.

## Smoke tests vs. real tests

`playbook-<pkg>-test.yml` is meant to be a **real functional test** of the
package (verify the actual behavior it ships, e.g. an LDAP query returns the
expected sudo rule, a homedir gets auto-created on first login). Write one
whenever you can stand up the scenario without disproportionate effort.

Where a full functional test isn't feasible yet (see
`playbook-nextcloud_samba-test.yml` for the current example — it needs a real
Nextcloud instance via App Center plus a reachable Samba share, which is a
substantial follow-up), fall back to a **smoke test**: assert the package
actually installed and wired itself up (e.g. its listener module is registered
with `univention-directory-listener-ctrl list`), so a packaging/postinst
regression doesn't go unnoticed even before the real test exists. Leave a
comment in the test playbook explaining what a real test would need and why
it's not there yet, so the gap doesn't get forgotten — don't let a smoke test
quietly stand in permanently for a real one without that note.

## Adding a new package group

1. Add a `.<pkg>_changes: &<PKG>_CHANGES` anchor near the top of
   `.gitlab-ci.yml`, listing the package's directories plus
   `_test-environment/**/*`.
2. Add a cfg under `configs/` (clone the closest existing group — most
   single-VM packages can reuse a `generic-5.cfg` section as a starting point;
   multi-VM packages like nextcloud-samba need one section per role). Point
   `proxmox_template` at the right `template-ucs-joined-5.2-6-<role>`.
3. Add `ansible/playbook-<pkg>.yml` (install) and `ansible/playbook-<pkg>-test.yml`
   (smoke or real test, per above).
4. Add the five jobs (`create_vms_<pkg>`, `configure_aptly_<pkg>`,
   `run_playbooks_<pkg>`, `test_<pkg>`, `terminate_<pkg>`) to `.gitlab-ci.yml`,
   following the `sudo_ldap` block as the template. Set `TDP_ENV_NAME: <pkg>`
   **and** `ENV_CFG` on all five jobs, not just `create_vms_<pkg>`/`terminate_<pkg>`
   — TDP's `ensure_host_availability` gate (used by `configure_aptly_<pkg>`/
   `run_playbooks_<pkg>`/`test_<pkg>` too) needs `ENV_CFG` to restart/verify the
   VMs before each of those jobs runs; without it the job fails fast with
   "Deployment is active but hosts are unreachable" even though the VMs are
   fine. Wire `on_stop: terminate_<pkg>` on `create_vms_<pkg>`'s `environment:`.
5. If the package's own behavior changed (not just its test coverage), update
   its `README.md` too — the test environment documents *how it's tested*, not
   *how it's used*.
