"""Issue an emergency one-time recovery link from the server terminal."""
import argparse
from urllib.parse import quote

from . import store


def main():
    parser=argparse.ArgumentParser(description="Crear un enlace de recuperación para una cuenta de Tablio")
    parser.add_argument("--email",required=True)
    parser.add_argument("--organization-id")
    parser.add_argument("--base-url",default="http://127.0.0.1:8000")
    args=parser.parse_args()
    store.initialize()
    with store.connection() as db:
        rows=list(db.execute("""SELECT o.id,o.name FROM organizations o JOIN memberships m ON m.organization_id=o.id
            JOIN users u ON u.id=m.user_id WHERE u.email=? AND u.disabled=0""",(args.email.strip().casefold(),)))
    if not rows: raise SystemExit("No hay una cuenta activa con ese email.")
    if args.organization_id:
        selected=next((r for r in rows if r["id"]==args.organization_id),None)
        if not selected: raise SystemExit("La cuenta no pertenece a esa organización.")
    elif len(rows)==1: selected=rows[0]
    else:
        print("La cuenta pertenece a varias organizaciones. Repetí con --organization-id:")
        for row in rows: print(f"{row['id']}  {row['name']}")
        return
    token=store.create_reset_token(selected["id"],args.email)
    print("Enlace de un solo uso, válido por una hora. Compartilo solo con la persona titular:")
    print(args.base_url.rstrip("/")+"/#access="+quote(token))


if __name__=="__main__": main()
