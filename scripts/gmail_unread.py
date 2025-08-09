#!/usr/bin/env python3
"""
Script pour lister les emails non lus depuis Gmail
Utilise la librairie GmailManager pour récupérer et afficher les emails non lus
"""

import argparse
from datetime import datetime
from app.sources.gmail_manager import GmailManager


def format_date(date_str):
    """Formate une date pour l'affichage"""
    try:
        # Parse la date Gmail et la formate
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return date_str


def format_sender(sender):
    """Formate l'expéditeur pour l'affichage"""
    # Extrait le nom et l'email
    if "<" in sender and ">" in sender:
        name = sender.split("<")[0].strip().strip('"')
        email = sender.split("<")[1].split(">")[0]
        if name:
            return f"{name} <{email}>"
        else:
            return email
    return sender


def display_email(email, show_body=False, max_body_length=200):
    """Affiche un email formaté"""
    print("=" * 80)
    print(f"📧 ID: {email['id']}")
    print(f"👤 De: {format_sender(email['sender'])}")
    print(f"📝 Objet: {email['subject']}")
    print(f"📅 Date: {format_date(email['date'])}")
    print(f"🏷️  Libellés: {', '.join(email['labels']) if email['labels'] else 'Aucun'}")

    if show_body and email["body"]:
        body_preview = email["body"][:max_body_length]
        if len(email["body"]) > max_body_length:
            body_preview += "..."
        print(f"📄 Contenu: {body_preview}")

    print(f"💬 Aperçu: {email['snippet']}")
    print("-" * 80)


def list_unread_emails(
    max_results=10,
    show_body=False,
    mark_as_read=False,
    filter_sender=None,
    filter_subject=None,
    quiet=False,
):
    """
    Liste les emails non lus

    Args:
        max_results (int): Nombre maximum d'emails à afficher
        show_body (bool): Afficher le contenu du corps de l'email
        mark_as_read (bool): Marquer les emails comme lus après affichage
        filter_sender (str): Filtrer par expéditeur
        filter_subject (str): Filtrer par objet
        quiet (bool): Mode silencieux (pas d'affichage détaillé)
    """
    try:
        # Initialisation du gestionnaire Gmail
        if not quiet:
            print("🔐 Connexion à Gmail...")

        gmail = GmailManager()

        if not quiet:
            print("📥 Récupération des emails non lus...")

        # Récupération des emails non lus
        unread_emails = gmail.get_unread_emails(max_results=max_results)

        if not unread_emails:
            print("✅ Aucun email non lu trouvé")
            return

        # Filtrage si demandé
        if filter_sender:
            unread_emails = [
                e for e in unread_emails if filter_sender.lower() in e["sender"].lower()
            ]

        if filter_subject:
            unread_emails = [
                e
                for e in unread_emails
                if filter_subject.lower() in e["subject"].lower()
            ]

        if not unread_emails:
            print("✅ Aucun email non lu correspondant aux filtres")
            return

        # Affichage des résultats
        if not quiet:
            print(f"\n📬 {len(unread_emails)} email(s) non lu(s) trouvé(s):")
            print("=" * 80)

        # Affichage des emails
        for i, email in enumerate(unread_emails, 1):
            if not quiet:
                print(f"\n{i}. ", end="")
                display_email(email, show_body=show_body)
            else:
                # Mode silencieux - affichage compact
                sender = format_sender(email["sender"])
                subject = (
                    email["subject"][:50] + "..."
                    if len(email["subject"]) > 50
                    else email["subject"]
                )
                date = format_date(email["date"])
                print(f"{i:2d}. {sender:<30} | {subject:<50} | {date}")

        # Marquage comme lu si demandé
        if mark_as_read and unread_emails:
            email_ids = [email["id"] for email in unread_emails]
            if gmail.mark_as_read(email_ids):
                if not quiet:
                    print(f"\n✅ {len(email_ids)} email(s) marqué(s) comme lu(s)")

        if not quiet:
            print(f"\n📊 Résumé: {len(unread_emails)} email(s) non lu(s) affiché(s)")

    except FileNotFoundError as e:
        print(f"❌ Erreur de configuration: {e}")
        print(
            "Assurez-vous que le fichier credentials.json est présent dans le répertoire"
        )
    except Exception as e:
        print(f"❌ Erreur: {e}")


def main():
    """Fonction principale avec gestion des arguments"""
    parser = argparse.ArgumentParser(
        description="Liste les emails non lus depuis Gmail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s                    # Liste les 10 premiers emails non lus
  %(prog)s -n 20              # Liste les 20 premiers emails non lus
  %(prog)s --body             # Affiche le contenu des emails
  %(prog)s --mark-read        # Marque les emails comme lus après affichage
  %(prog)s --sender "gmail"   # Filtre par expéditeur contenant "gmail"
  %(prog)s --subject "facture" # Filtre par objet contenant "facture"
  %(prog)s -q                  # Mode silencieux (affichage compact)
        """,
    )

    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=10,
        help="Nombre maximum d'emails à afficher (défaut: 10)",
    )

    parser.add_argument(
        "--body", action="store_true", help="Afficher le contenu du corps des emails"
    )

    parser.add_argument(
        "--mark-read",
        action="store_true",
        help="Marquer les emails comme lus après affichage",
    )

    parser.add_argument(
        "--sender", type=str, help="Filtrer par expéditeur (recherche partielle)"
    )

    parser.add_argument(
        "--subject", type=str, help="Filtrer par objet (recherche partielle)"
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Mode silencieux (affichage compact)"
    )

    parser.add_argument("--version", action="version", version="%(prog)s 1.0")

    args = parser.parse_args()

    # Affichage de l'en-tête
    if not args.quiet:
        print("📧 Gmail Unread Emails Lister")
        print("=" * 50)
        print(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print()

    # Exécution de la fonction principale
    list_unread_emails(
        max_results=args.max_results,
        show_body=args.body,
        mark_as_read=args.mark_read,
        filter_sender=args.sender,
        filter_subject=args.subject,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
