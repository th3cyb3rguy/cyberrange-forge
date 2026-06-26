# ============================================================
# CyberRange Forge
# Cross-platform cybersecurity lab generator
# Supports Linux, macOS, and Windows
# Created June 16, 2026 by th3cyb3rguy, llc
# CyberRange Forge is an open-source project.
# ============================================================

from pathlib import Path
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

app = typer.Typer(
    help="""
CyberRange Forge v1.0

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

    console.print("[bold cyan]CyberRange Forge v1.0.0[/bold cyan]")
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
# ============================================================

LABS = {
    "phishing-triage": {
        "title": "Phishing Triage Lab",
        "description": "Analyze suspicious email indicators and create defensive detections.",
        "services": ["mailhog", "analyst-workstation", "email-seeder"],
    },
    "web-detection": {
        "title": "Web Attack Detection Lab",
        "description": "Review web logs and identify suspicious HTTP activity.",
        "services": ["nginx", "log-generator"],
    },
    "linux-intrusion": {
        "title": "Linux Intrusion Lab",
        "description": "Investigate SSH brute-force and Linux persistence indicators.",
        "services": ["ubuntu-victim", "log-generator"],
    },
}

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
# Displays all available lab templates
# ============================================================

@app.command()
def list_labs():
    """List available cyber lab templates."""
    table = Table(title="Available CyberRange Forge Labs")
    table.add_column("Lab ID", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Description")

    for lab_id, lab in LABS.items():
        table.add_row(lab_id, lab["title"], lab["description"])

    console.print(table)

# ============================================================
# CLI Command: validate
# Checks local system readiness before generating labs
# ============================================================

@app.command()
def validate():
    """Verify Python, Docker,and template availability."""
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

    output_path.mkdir(parents=True)

    context = {
        "lab_id": lab,
        "lab_name": safe_name,
        "difficulty": difficulty,
        "title": LABS[lab]["title"],
        "description": LABS[lab]["description"],
        "services": LABS[lab]["services"],
    }

    render_lab(template_dir, output_path, context)

    metadata = output_path / "lab.yml"
    metadata.write_text(yaml.dump(context, sort_keys=False), encoding="utf-8")

    console.print(f"[green]Generated lab:[/green] {output_path}")
    console.print()
    console.print("Next commands:")
    console.print(f"  cd {output_path}")
    console.print("  docker compose up -d")

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
