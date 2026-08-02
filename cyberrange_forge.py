# ============================================================
# CyberRange Forge
# Cross-platform cybersecurity lab generator
# Supports Linux, macOS, and Windows
# Created June 16, 2026 by th3cyb3rguy, llc
# CyberRange Forge is an open-source project.
# ============================================================

from pathlib import Path
import socket
import zipfile
import shutil
import subprocess
import sys

import typer
import yaml
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table

# ============================================================
# Application Setup
# Creates the CLI app and console output handler
# ============================================================
APP_VERSION = "1.0.1"

app = typer.Typer(
    help=f"""
    CyberRange Forge v{APP_VERSION}

    Defensive Cybersecurity Lab Generator.

    Run 'list-labs' to see templates.

    Defensive use only.
    """
)

console = Console()

# ============================================================
# Banner
# Displays the CyberRange Forge startup banner
# ============================================================
def print_banner():
    if command_exists("toilet"):
        subprocess.run(
            [
                "toilet",
                "-f",
                "future",
                "-F",
                "metal",
                "-F",
                "border",
                "CYBERRANGE FORGE",
            ],
            check=False,
        )
    else:
        console.print("[bold cyan]CyberRange Forge[/bold cyan]")

    # --------------------------------------------------------
    # Version Information
    # --------------------------------------------------------
    console.print(f"[bold cyan]CyberRange Forge v{APP_VERSION}[/bold cyan]")
    console.print("[white]Defensive Cybersecurity Lab Generator[/white]")
    console.print()

# ============================================================
# Path Configuration
# Defines important project folders
# ============================================================
BASE_DIR = Path(__file__).parent.resolve()
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
EXPORT_DIR = BASE_DIR / "exports"

# ============================================================
# Lab Registry
# Defines available lab templates and metadata
#
# ports:       host ports this lab exposes, mapped to a
#              friendly service name used in conflict warnings
# volume_dirs: host-side directories that container services
#              write into; pre-created by CyberRange Forge so
#              Docker never auto-creates them as root
# ============================================================
LABS = {
    "phishing-triage": {
        "category": "blue",
        "title": "Phishing Triage Lab",
        "description": "Analyze suspicious email indicators and create defensive detections.",
        "services": ["mailhog", "analyst-workstation", "email-seeder"],
        "ports": {
            8025: "MailHog Web UI",
            1025: "MailHog SMTP",
        },
        "volume_dirs": [],
    },
    "web-detection": {
        "category": "blue",
        "title": "Web Attack Detection Lab",
        "description": "Review web logs and identify suspicious HTTP activity.",
        "services": ["nginx", "log-generator"],
        "ports": {
            8080: "Web Server (Nginx)",
        },
        "volume_dirs": ["logs"],
    },
    "linux-intrusion": {
        "category": "blue",
        "title": "Linux Intrusion Lab",
        "description": "Investigate SSH brute-force and Linux persistence indicators.",
        "services": ["ubuntu-victim", "log-generator"],
        "ports": {},
        "volume_dirs": ["logs", "artifacts"],
    },
}

# ============================================================
# Red Team Roadmap
# Announced but not yet implemented. No templates, no
# functionality. Listed here only for 'list-labs' output.
# ============================================================
RED_TEAM_ROADMAP = [
    "phishing-simulation",
    "web-assessment",
    "linux-postexploitation",
]

# ============================================================
# Output File Overrides
# Allows selected template files to be renamed during generation
# Example: diagram.mmd.j2 -> network-diagram.mmd
# ============================================================
OUTPUT_NAME_MAP = {
    "diagram.mmd": "network-diagram.mmd",
}

# ============================================================
# Utility: Safe Lab Name
# Converts user-provided names into safe folder/container names
# ============================================================
def safe_lab_name(name: str) -> str:
    cleaned = name.lower().replace(" ", "-").replace("_", "-")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
    cleaned = "".join(char for char in cleaned if char in allowed)
    return cleaned.strip("-") or "cyber-lab"

# ============================================================
# Utility: Command Checker
# Checks whether required system commands are available
# ============================================================
def command_exists(command: str) -> bool:
    return shutil.which(command) is not None

# ============================================================
# Utility: Run Command
# Runs a command safely and returns success/failure plus output
# ============================================================
def run_command(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except Exception as error:
        return False, str(error)

# ============================================================
# Utility: Port Availability Check
# Confirms whether a TCP port is currently free on localhost
# ============================================================
def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False

# ============================================================
# Utility: Friendly Port Conflict Warning
# Replaces raw Docker bind errors with clear guidance
# ============================================================
def warn_port_conflict(port: int, service_name: str) -> None:
    console.print()
    console.print(f"[yellow]Port {port} is already in use.[/yellow]")
    console.print()
    console.print(f"Another {service_name} instance appears to be running.")
    console.print()
    console.print("Try:")
    console.print()
    console.print("  docker compose down")
    console.print()
    console.print("or")
    console.print()
    console.print("  docker stop <container>")
    console.print()
    console.print("Then launch the lab again.")
    console.print()

# ============================================================
# Template Renderer
# Automatically renders every .j2 file inside a selected lab
# Preserves folders and removes the .j2 extension
# ============================================================
def render_lab(template_dir: Path, output_path: Path, context: dict) -> None:
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    for template_file in template_dir.rglob("*.j2"):
        relative_template = template_file.relative_to(template_dir)
        output_name = str(relative_template).removesuffix(".j2")

        if output_name in OUTPUT_NAME_MAP:
            output_name = OUTPUT_NAME_MAP[output_name]

        destination = output_path / output_name
        destination.parent.mkdir(parents=True, exist_ok=True)

        template = env.get_template(str(relative_template))
        destination.write_text(template.render(**context), encoding="utf-8")

# ============================================================
# Utility: Pre-create Volume Directories
# Creates host-side bind-mount directories as the invoking
# user *before* Docker ever starts a container. This prevents
# Docker from auto-creating them as root, which is what forces
# `sudo rm -rf` on generated labs.
# ============================================================
def prepare_volume_dirs(output_path: Path, volume_dirs: list[str]) -> None:
    for dir_name in volume_dirs:
        (output_path / dir_name).mkdir(parents=True, exist_ok=True)

# ============================================================
# Validation: Python Version
# Ensures the user has Python 3.10 or newer
# ============================================================
def validate_python() -> tuple[bool, str]:
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return (
        False,
        f"Python {version.major}.{version.minor}.{version.micro} detected; Python 3.10+ required",
    )

# ============================================================
# Validation: Docker
# Checks whether Docker is installed and responding
# ============================================================
def validate_docker() -> tuple[bool, str]:
    if not command_exists("docker"):
        return False, "Docker command not found"
    ok, output = run_command(["docker", "--version"])
    if not ok:
        return False, output or "Docker is installed but not responding"
    return True, output

# ============================================================
# Validation: Docker Compose
# Checks whether Docker Compose is available
# Supports both modern `docker compose` and legacy `docker-compose`
# ============================================================
def validate_docker_compose() -> tuple[bool, str]:
    ok, output = run_command(["docker", "compose", "version"])
    if ok:
        return True, output
    if command_exists("docker-compose"):
        ok, output = run_command(["docker-compose", "--version"])
        if ok:
            return True, output
    return False, "Docker Compose not found"

# ============================================================
# Validation: Template Folders
# Verifies that all registered lab templates exist
# ============================================================
def validate_templates() -> tuple[bool, str]:
    missing = []
    for lab_id in LABS:
        template_dir = TEMPLATES_DIR / lab_id
        if not template_dir.exists():
            missing.append(lab_id)
    if missing:
        return False, f"Missing templates: {', '.join(missing)}"
    return True, "All registered templates found"

# ============================================================
# Validation: Template Files
# Checks that each template contains at least one .j2 file
# ============================================================
def validate_template_files() -> tuple[bool, str]:
    empty_templates = []
    for lab_id in LABS:
        template_dir = TEMPLATES_DIR / lab_id
        if template_dir.exists() and not list(template_dir.rglob("*.j2")):
            empty_templates.append(lab_id)
    if empty_templates:
        return False, f"No .j2 files found in: {', '.join(empty_templates)}"
    return True, "Template files found"

# ============================================================
# CLI Command: list-labs
# Displays available lab templates, grouped by team
# Red Team labs are roadmap only -- no templates ship yet
# ============================================================
@app.command()
def list_labs():
    """List available cyber lab templates."""
    title = "CyberRange Forge Labs"
    console.print(f"[bold]{title}[/bold]")
    console.print("=" * len(title))
    console.print()

    blue_header = "Blue Team Labs"
    console.print(f"[bold cyan]{blue_header}[/bold cyan]")
    console.print("-" * len(blue_header))
    console.print()
    for lab_id in LABS:
        console.print(lab_id)
    console.print()

    red_header = "Red Team Labs (Coming Soon)"
    console.print(f"[bold yellow]{red_header}[/bold yellow]")
    console.print("-" * len(red_header))
    console.print()
    for lab_id in RED_TEAM_ROADMAP:
        console.print(lab_id)

# ============================================================
# CLI Command: validate
# Checks local system readiness before generating labs
# ============================================================
@app.command()
def validate():
    """Verify Python, Docker, and template availability."""
    checks = {
        "Python Version": validate_python(),
        "Docker": validate_docker(),
        "Docker Compose": validate_docker_compose(),
        "Toilet (Optional)": (
            True,
            "Installed"
        ) if command_exists("toilet") else (
            True,
            "Not installed (fallback banner will be used)"
        ),
        "Template Folders": validate_templates(),
        "Template Files": validate_template_files(),
    }

    table = Table(title="CyberRange Forge Validation")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")

    all_passed = True
    for check_name, result in checks.items():
        passed, details = result
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        if not passed:
            all_passed = False
        table.add_row(check_name, status, details)

    console.print(table)

    if not all_passed:
        console.print("[red]Validation failed. Fix the issues above before running a lab.[/red]")
        raise typer.Exit(1)

    console.print("[green]All validation checks passed.[/green]")

# ============================================================
# CLI Command: create
# Generates a selected cybersecurity lab from templates
# ============================================================
@app.command()
def create(
    lab: str = typer.Argument(..., help="Lab template name"),
    name: str = typer.Option("owlsec-demo", "--name", "-n", help="Generated lab name"),
    difficulty: str = typer.Option(
        "beginner",
        "--difficulty",
        "-d",
        help="beginner or intermediate",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing output"),
):
    """Generate a local cybersecurity lab."""
    if lab not in LABS:
        console.print(f"[red]Unknown lab:[/red] {lab}")
        console.print("Run: python cyberrange_forge.py list-labs")
        raise typer.Exit(1)

    if difficulty not in {"beginner", "intermediate"}:
        console.print("[red]Difficulty must be beginner or intermediate.[/red]")
        raise typer.Exit(1)

    template_dir = TEMPLATES_DIR / lab
    if not template_dir.exists():
        console.print(f"[red]Missing template directory:[/red] {template_dir}")
        raise typer.Exit(1)

    safe_name = safe_lab_name(name)
    output_path = OUTPUT_DIR / safe_name

    if output_path.exists():
        if not overwrite:
            console.print(f"[yellow]Output already exists:[/yellow] {output_path}")
            console.print("Use --overwrite to replace it.")
            raise typer.Exit(1)
        shutil.rmtree(output_path)

    # --------------------------------------------------------
    # Friendly Port Conflict Detection
    # Checked before generation so the warning is seen up front
    # instead of surfacing as a raw Docker bind error later
    # --------------------------------------------------------
    for port, service_name in LABS[lab]["ports"].items():
        if not port_available(port):
            warn_port_conflict(port, service_name)

    output_path.mkdir(parents=True)

    context = {
        "lab_id": lab,
        "lab_name": safe_name,
        "difficulty": difficulty,
        "title": LABS[lab]["title"],
        "description": LABS[lab]["description"],
        "services": LABS[lab]["services"],
        "generator_version": APP_VERSION,
    }

    render_lab(template_dir, output_path, context)

    # --------------------------------------------------------
    # Pre-create bind-mount directories as the invoking user
    # so Docker never auto-creates them as root
    # --------------------------------------------------------
    prepare_volume_dirs(output_path, LABS[lab]["volume_dirs"])

    metadata = output_path / "lab.yml"
    metadata.write_text(yaml.dump(context, sort_keys=False), encoding="utf-8")

    console.print(f"[green]Lab generated successfully:[/green] {output_path}")
    console.print()
    console.print("To start:")
    console.print()
    console.print(f"  cd {output_path}")
    console.print("  docker compose up -d")
    console.print()
    console.print("[bold]Reminder[/bold]")
    console.print("-" * len("Reminder"))
    console.print()
    console.print("When finished with this lab, stop it using:")
    console.print()
    console.print("  docker compose down")
    console.print()
    console.print("Stopping labs prevents Docker port conflicts when launching another lab.")

# ============================================================
# CLI Command: export
# Exports a generated lab as a ZIP archive
# ============================================================
@app.command()
def export(
    lab_name: str = typer.Argument(
        ...,
        help="Generated lab name inside output/"
    )
):
    """Export a generated lab as a ZIP file."""
    source_dir = OUTPUT_DIR / lab_name
    if not source_dir.exists():
        console.print(
            f"[red]Lab not found:[/red] {source_dir}"
        )
        raise typer.Exit(1)

    EXPORT_DIR.mkdir(exist_ok=True)
    zip_path = EXPORT_DIR / f"{lab_name}.zip"

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as archive:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                archive.write(
                    file_path,
                    file_path.relative_to(source_dir)
                )

    console.print(
        f"[green]Export complete:[/green] {zip_path}"
    )

# ============================================================
# Program Entry Point
# Displays banner and starts CLI
# ============================================================
if __name__ == "__main__":
    print_banner()
    app()
