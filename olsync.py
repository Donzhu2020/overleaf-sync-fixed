"""Overleaf Two-Way Sync Tool"""
##################################################
# MIT License
##################################################
# File: olsync.py
# Description: Overleaf Two-Way Sync
# Author: Moritz Glöckl (fixes by Donzhu2020)
# License: MIT
# Version: 1.2.1
##################################################

import click
import os
from yaspin import yaspin
import pickle
import zipfile
import io
import dateutil.parser
import glob
import fnmatch
import traceback
from pathlib import Path

try:                              # pip-installed package
    from olsync.olclient import OverleafClient
    import olsync.olbrowserlogin as olbrowserlogin
except ImportError:               # development / editable install
    from olclient import OverleafClient
    import olbrowserlogin


# ------------------------------------------------------------------ #
# CLI entry-point
# ------------------------------------------------------------------ #

@click.group(invoke_without_command=True)
@click.option('-l', '--local-only', 'local', is_flag=True,
              help="Sync local project files to Overleaf only.")
@click.option('-r', '--remote-only', 'remote', is_flag=True,
              help="Sync remote project files from Overleaf to local file system only.")
@click.option('-n', '--name', 'project_name', default="",
              help="Overleaf project name (defaults to the current directory name).")
@click.option('--store-path', 'cookie_path', default=".olauth",
              type=click.Path(exists=False),
              help="Relative path to the persisted Overleaf cookie file.")
@click.option('-p', '--path', 'sync_path', default=".",
              type=click.Path(exists=True),
              help="Path of the project to sync.")
@click.option('-i', '--olignore', 'olignore_path', default=".olignore",
              type=click.Path(exists=False),
              help="Path to the .olignore file (ignored when syncing remote→local). "
                   "Uses fnmatch / unix filename pattern matching.")
@click.option('-v', '--verbose', 'verbose', is_flag=True,
              help="Enable extended error logging.")
@click.version_option(package_name='overleaf-sync')
@click.pass_context
def main(ctx, local, remote, project_name, cookie_path, sync_path, olignore_path, verbose):
    if ctx.invoked_subcommand is not None:
        return

    if not os.path.isfile(cookie_path):
        raise click.ClickException(
            "Persisted Overleaf cookie not found. Please login or check --store-path."
        )

    # FIX: open() used as context manager so the file is always closed
    with open(cookie_path, 'rb') as f:
        store = pickle.load(f)

    overleaf_client = OverleafClient(store["cookie"], store["csrf"])

    os.chdir(sync_path)
    project_name = project_name or os.path.basename(os.getcwd())

    project = execute_action(
        lambda: overleaf_client.get_project(project_name),
        "Querying project",
        "Project queried successfully.",
        "Project could not be queried.",
        verbose,
    )

    project_infos = execute_action(
        lambda: overleaf_client.get_project_infos(project["id"]),
        "Querying project details",
        "Project details queried successfully.",
        "Project details could not be queried.",
        verbose,
    )

    zip_file = execute_action(
        lambda: zipfile.ZipFile(io.BytesIO(overleaf_client.download_project(project["id"]))),
        "Downloading project",
        "Project downloaded successfully.",
        "Project could not be downloaded.",
        verbose,
    )

    sync = not (local or remote)

    if remote or sync:
        sync_func(
            files_from=zip_file.namelist(),
            deleted_files=[
                f for f in olignore_keep_list(olignore_path)
                if f not in zip_file.namelist() and not sync
            ],
            # FIX: open file with context manager inside lambda to avoid leak
            create_file_at_to=lambda name: write_file(name, zip_file.read(name)),
            delete_file_at_to=lambda name: delete_file(name),
            create_file_at_from=lambda name: overleaf_client.upload_file(
                project["id"], project_infos, name,
                os.path.getsize(name),
                open(name, 'rb'),   # file handle; requests closes it after upload
            ),
            from_exists_in_to=lambda name: os.path.isfile(name),
            from_equal_to_to=lambda name: _read_local(name) == zip_file.read(name),
            from_newer_than_to=lambda name: (
                dateutil.parser.isoparse(project["lastUpdated"]).timestamp()
                > os.path.getmtime(name)
            ),
            from_name="remote",
            to_name="local",
            verbose=verbose,
        )

    if local or sync:
        # FIX: call olignore_keep_list once and reuse the result to avoid
        #      redundant filesystem scans inside lambdas
        keep_list = olignore_keep_list(olignore_path)
        remote_names = zip_file.namelist()

        sync_func(
            files_from=keep_list,
            deleted_files=[
                f for f in remote_names
                if f not in keep_list and not sync
            ],
            create_file_at_to=lambda name: overleaf_client.upload_file(
                project["id"], project_infos, name,
                os.path.getsize(name),
                open(name, 'rb'),
            ),
            delete_file_at_to=lambda name: overleaf_client.delete_file(
                project["id"], project_infos, name
            ),
            create_file_at_from=lambda name: write_file(name, zip_file.read(name)),
            from_exists_in_to=lambda name: name in remote_names,
            from_equal_to_to=lambda name: _read_local(name) == zip_file.read(name),
            from_newer_than_to=lambda name: (
                os.path.getmtime(name)
                > dateutil.parser.isoparse(project["lastUpdated"]).timestamp()
            ),
            from_name="local",
            to_name="remote",
            verbose=verbose,
        )


# ------------------------------------------------------------------ #
# Sub-commands
# ------------------------------------------------------------------ #

@main.command()
@click.option('--path', 'cookie_path', default=".olauth",
              type=click.Path(exists=False),
              help="Path to store the persisted Overleaf cookie.")
@click.option('-v', '--verbose', 'verbose', is_flag=True,
              help="Enable extended error logging.")
def login(cookie_path, verbose):
    if os.path.isfile(cookie_path) and not click.confirm(
        'Persisted Overleaf cookie already exists. Override?'
    ):
        return
    click.clear()
    execute_action(
        lambda: login_handler(cookie_path),
        "Login",
        "Login successful. Cookie persisted as `{}`.\nYou may now sync your project.".format(
            click.format_filename(cookie_path)
        ),
        "Login failed. Please try again.",
        verbose,
    )


@main.command(name='list')
@click.option('--store-path', 'cookie_path', default=".olauth",
              type=click.Path(exists=False),
              help="Relative path to load the persisted Overleaf cookie.")
@click.option('-v', '--verbose', 'verbose', is_flag=True,
              help="Enable extended error logging.")
def list_projects(cookie_path, verbose):
    if not os.path.isfile(cookie_path):
        raise click.ClickException(
            "Persisted Overleaf cookie not found. Please login or check --store-path."
        )

    with open(cookie_path, 'rb') as f:
        store = pickle.load(f)

    overleaf_client = OverleafClient(store["cookie"], store["csrf"])

    def query_projects():
        projects = sorted(
            overleaf_client.all_projects(),
            key=lambda x: x['lastUpdated'],
            reverse=True,
        )
        click.echo("")
        for p in projects:
            ts = dateutil.parser.isoparse(p['lastUpdated']).strftime('%m/%d/%Y, %H:%M:%S')
            click.echo(f"{ts} - {p['name']}")
        return True

    click.clear()
    execute_action(
        query_projects,
        "Querying all projects",
        "Querying all projects successful.",
        "Querying all projects failed. Please try again.",
        verbose,
    )


@main.command(name='download')
@click.argument('project_name', required=False)
@click.option('--pdf', is_flag=True,
              help="Download compiled PDF instead of source code.")
@click.option('--path', 'download_path', default=".",
              type=click.Path(exists=True),
              help="Directory to download to.")
@click.option('--store-path', 'cookie_path', default=".olauth",
              type=click.Path(exists=False),
              help="Relative path to load the persisted Overleaf cookie.")
@click.option('-v', '--verbose', 'verbose', is_flag=True,
              help="Enable extended error logging.")
def download(project_name, pdf, download_path, cookie_path, verbose):
    """Download project source (default) or compiled PDF (--pdf)."""
    if not os.path.isfile(cookie_path):
        raise click.ClickException(
            "Persisted Overleaf cookie not found. Please login or check --store-path."
        )

    with open(cookie_path, 'rb') as f:
        store = pickle.load(f)

    overleaf_client = OverleafClient(store["cookie"], store["csrf"])
    project_name = project_name or os.path.basename(os.getcwd())

    project = execute_action(
        lambda: overleaf_client.get_project(project_name),
        "Querying project",
        "Project queried successfully.",
        "Project could not be queried.",
        verbose,
    )

    if pdf:
        result = execute_action(
            lambda: overleaf_client.download_pdf(project["id"]),
            "Compiling and downloading PDF",
            "PDF downloaded successfully.",
            "PDF could not be downloaded.",
            verbose,
        )
        if result:
            file_name, content = result
            target_path = os.path.join(download_path, file_name)
            with open(target_path, 'wb') as f:
                f.write(content)
            click.echo(f"\n✅ Saved PDF to: {target_path}")
    else:
        content = execute_action(
            lambda: overleaf_client.download_project(project["id"]),
            "Downloading project source",
            "Source downloaded successfully.",
            "Source could not be downloaded.",
            verbose,
        )
        # FIX: extract into a subfolder named after the project, not the bare
        # download_path, so files don't spill into the current directory.
        safe_name = "".join(c for c in project["name"] if c.isalnum() or c in " _-").strip()
        project_dir = os.path.join(download_path, safe_name)
        os.makedirs(project_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            z.extractall(project_dir)
        click.echo(f"\n✅ Extracted source to: {os.path.abspath(project_dir)}")


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def login_handler(path):
    store = olbrowserlogin.login()
    if store is None:
        return False
    with open(path, 'wb+') as f:
        pickle.dump(store, f)
    return True


def _read_local(path):
    """Read a local file and return its bytes. Used inside lambdas."""
    with open(path, 'rb') as f:
        return f.read()


def delete_file(path):
    """Delete a local file if it exists, silently skip directories."""
    _dir = os.path.dirname(path)
    if _dir == path:        # path is a bare directory name
        return
    if _dir != '' and not os.path.exists(_dir):
        return
    if os.path.isfile(path):
        os.remove(path)


def write_file(path, content):
    """Write *content* bytes to *path*, creating parent directories as needed."""
    _dir = os.path.dirname(path)
    if _dir == path:        # path is a bare directory name
        return
    if _dir != '' and not os.path.exists(_dir):
        os.makedirs(_dir)
    with open(path, 'wb+') as f:
        f.write(content)


def sync_func(
    files_from,
    deleted_files,
    create_file_at_to,
    delete_file_at_to,
    create_file_at_from,
    from_exists_in_to,
    from_equal_to_to,
    from_newer_than_to,
    from_name,
    to_name,
    verbose=False,
):
    click.echo("\nSyncing files from [%s] to [%s]" % (from_name, to_name))
    click.echo('=' * 40)

    newly_add_list = []
    update_list = []
    delete_list = []
    restore_list = []
    not_restored_list = []
    not_sync_list = []
    synced_list = []

    for name in files_from:
        if from_exists_in_to(name):
            if not from_equal_to_to(name):
                if not from_newer_than_to(name) and not click.confirm(
                    '\n-> Warning: [%s] from [%s] is older than [%s].\n'
                    'Continue to overwrite with the older version?' % (name, from_name, to_name)
                ):
                    not_sync_list.append(name)
                    continue
                update_list.append(name)
            else:
                synced_list.append(name)
        else:
            newly_add_list.append(name)

    for name in deleted_files:
        choice = click.prompt(
            '\n-> Warning: <%s> no longer exists on [%s] (still present on [%s]).\n'
            'Should the file be [d]eleted, [r]estored, or [i]gnored?' % (name, from_name, to_name),
            default="i",
            type=click.Choice(['d', 'r', 'i']),
        )
        if choice == "d":
            delete_list.append(name)
        elif choice == "r":
            restore_list.append(name)
        else:
            not_restored_list.append(name)

    # --- create new files on [to] ---
    click.echo("\n[NEW] Following new file(s) created on [%s]" % to_name)
    for name in newly_add_list:
        click.echo("\t%s" % name)
        try:
            create_file_at_to(name)
        except Exception:
            if verbose:
                print(traceback.format_exc())
            raise click.ClickException(
                "\n[ERROR] An error occurred while creating new file(s) on [%s]" % to_name
            )

    # --- restore files on [from] ---
    click.echo("\n[NEW] Following file(s) restored on [%s]" % from_name)
    for name in restore_list:
        click.echo("\t%s" % name)
        try:
            create_file_at_from(name)
        except Exception:
            if verbose:
                print(traceback.format_exc())
            raise click.ClickException(
                "\n[ERROR] An error occurred while restoring file(s) on [%s]" % from_name
            )

    # --- update existing files on [to] ---
    click.echo("\n[UPDATE] Following file(s) updated on [%s]" % to_name)
    for name in update_list:
        click.echo("\t%s" % name)
        try:
            create_file_at_to(name)
        except Exception:
            if verbose:
                print(traceback.format_exc())
            raise click.ClickException(
                "\n[ERROR] An error occurred while updating file(s) on [%s]" % to_name
            )

    # --- delete files on [to] ---
    click.echo("\n[DELETE] Following file(s) deleted on [%s]" % to_name)
    for name in delete_list:
        click.echo("\t%s" % name)
        try:
            delete_file_at_to(name)
        except Exception:
            if verbose:
                print(traceback.format_exc())
            raise click.ClickException(
                "\n[ERROR] An error occurred while deleting file(s) on [%s]" % to_name
            )

    click.echo("\n[SYNC] Following file(s) are up to date")
    for name in synced_list:
        click.echo("\t%s" % name)

    click.echo("\n[SKIP] Following file(s) on [%s] were NOT synced to [%s]" % (from_name, to_name))
    for name in not_sync_list:
        click.echo("\t%s" % name)

    click.echo("\n[SKIP] Following file(s) on [%s] were NOT restored to [%s]" % (to_name, from_name))
    for name in not_restored_list:
        click.echo("\t%s" % name)

    click.echo("")
    click.echo("✅ Synced files from [%s] to [%s]" % (from_name, to_name))
    click.echo("")


def execute_action(action, progress_message, success_message, fail_message,
                   verbose_error_logging=False):
    """Run *action* inside a spinner; raise ClickException on failure."""
    with yaspin(text=progress_message, color="green") as spinner:
        try:
            result = action()
        except Exception:
            if verbose_error_logging:
                print(traceback.format_exc())
            result = False

        # FIX: treat falsy results (None, False, empty list) as failure
        if result is not None and result is not False:
            spinner.write(success_message)
            spinner.ok("✅ ")
        else:
            spinner.fail("💥 ")
            raise click.ClickException(fail_message)

    return result


def olignore_keep_list(olignore_path):
    """
    Return the list of local files to sync, after applying .olignore patterns.
    Only called when syncing local → remote.
    """
    # glob '**' returns directories too; filter them out
    files = glob.glob('**', recursive=True)
    click.echo("=" * 40)

    if not os.path.isfile(olignore_path):
        click.echo("\nNotice: .olignore not found – syncing all items.")
        keep_list = files
    else:
        click.echo("\n.olignore: filtering with %s" % olignore_path)
        with open(olignore_path, 'r') as f:
            ignore_patterns = [line for line in f.read().splitlines() if line]  # skip blank lines

        keep_list = [
            f for f in files
            if not any(fnmatch.fnmatch(f, pat) for pat in ignore_patterns)
        ]

    # Normalise separators and drop directories
    return [Path(item).as_posix() for item in keep_list if not os.path.isdir(item)]


if __name__ == "__main__":
    main()
