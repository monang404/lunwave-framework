import argparse
import sys
from lunawave_framework.cli.scaffold import scaffold_project, scaffold_module, scaffold_plugin, scaffold_adapter

def main():
    parser = argparse.ArgumentParser(description="LunaWave Framework CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new project
    parser_new = subparsers.add_parser("new", help="Scaffold a new LunaWave Framework project")
    parser_new.add_argument("name", help="Name of the project")
    
    # module:create
    parser_module = subparsers.add_parser("module:create", help="Create a new generic module")
    parser_module.add_argument("name", help="Name of the module")

    # plugin:create
    parser_plugin = subparsers.add_parser("plugin:create", help="Create a new plugin")
    parser_plugin.add_argument("name", help="Name of the plugin")

    # adapter:create
    parser_adapter = subparsers.add_parser("adapter:create", help="Create a new adapter")
    parser_adapter.add_argument("name", help="Name of the adapter")

    args = parser.parse_args()

    if args.command == "new":
        scaffold_project(args.name)
    elif args.command == "module:create":
        scaffold_module(args.name)
    elif args.command == "plugin:create":
        scaffold_plugin(args.name)
    elif args.command == "adapter:create":
        scaffold_adapter(args.name)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
