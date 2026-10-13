"""Create the first owner without exposing a public registration endpoint."""
import argparse
import getpass

from . import store


def main():
    parser=argparse.ArgumentParser(description="Inicializar el propietario de Tablio")
    parser.add_argument("--email",required=True)
    parser.add_argument("--name",required=True)
    parser.add_argument("--organization",default="Mi organización")
    args=parser.parse_args()
    store.initialize()
    password=getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    confirm=getpass.getpass("Repetí la contraseña: ")
    if password!=confirm: raise SystemExit("Las contraseñas no coinciden.")
    try:
        user_id,org_id=store.bootstrap_owner(args.email,args.name,password,args.organization)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Propietario creado. Usuario: {user_id}; organización: {org_id}")


if __name__=="__main__": main()
