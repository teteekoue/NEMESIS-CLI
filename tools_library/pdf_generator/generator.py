import argparse
import subprocess
import os
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def generate_pdf(template_name, data, output_path, is_custom=False):
    # Résolution intelligente du chemin de sortie
    out_path = Path(output_path).resolve()
    # Le fichier temporaire sera créé dans le même dossier que le PDF de sortie
    temp_html = out_path.parent / "temp_render.html"
    
    # 1. Préparation du HTML
    if is_custom:
        # On tente de résoudre le chemin du template (peut être absolu ou relatif)
        template_path = Path(template_name).resolve()
        html_content = template_path.read_text(encoding='utf-8')
    else:
        # Utilisation du moteur Jinja2 pour les templates standards
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template(f"{template_name}.html")
        html_content = template.render(data)
    
    # Écriture du fichier temporaire pour Firefox
    temp_html.write_text(html_content, encoding='utf-8')
    
    # 2. Conversion via Firefox (Headless Print)
    try:
        # Commande Firefox pour imprimer en PDF
        cmd = [
            "firefox",
            "--headless",
            "--no-remote",
            "--print", str(out_path),
            str(temp_html)
        ]

        # Augmentation du timeout à 90 secondes pour les systèmes plus lents
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

        if result.returncode == 0:
            print(f"Succès : PDF généré dans {out_path}")
        else:
            print(f"Erreur Firefox (code {result.returncode}) : {result.stderr}")
            exit(1)

    except subprocess.TimeoutExpired:
        print(f"Erreur : Délai d'attente dépassé (90s). Firefox est trop lent.")
        exit(1)
    except Exception as e:
        print(f"Erreur lors de la génération : {str(e)}")
        exit(1)
    finally:
        # Nettoyage du fichier temporaire
        if temp_html.exists():
            temp_html.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", help="Nom du template ou chemin HTML")
    parser.add_argument("--data", default='{}', help="Données JSON")
    parser.add_argument("--output", default="output.pdf")
    parser.add_argument("--custom", action="store_true")
    
    args = parser.parse_args()
    data = json.loads(args.data)
    
    generate_pdf(args.template, data, args.output, args.custom)
