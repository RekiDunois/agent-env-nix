{ pkgs, agentLib }:
let
  # A producer can equivalently receive mkAgentPackage through callPackage.
  base = agentLib.mkAgentPackage {
    inherit pkgs;
    id = "example-base";
    version = "0.1.0";
    files."skills/example" = ./skills/example;
    exports.skills.example = "skills/example";
    exports.agents.example = {
      description = "A minimal example agent.";
      developer_instructions = "Inspect the example skill. Report what its script prints.";
    };
    runtimePackages = [ pkgs.coreutils ];
  };
  tools = agentLib.mkAgentPackage {
    inherit pkgs;
    id = "example-tools";
    version = "0.1.0";
    files = { };
    agentDependencies = [ base ];
    # A named upstream server; the library does not copy its implementation.
    mcp.programs.fetch.enable = true;
  };
  # A real override, including the upstream named module's package/args path.
  overridden = tools.override {
    mcpOverrides = { lib, ... }: {
      programs.fetch.args = lib.mkForce [ "--user-agent=agent-env-nix-example" ];
    };
  };
in
{
  inherit base tools overridden;
  project = agentLib.mkProject { inherit pkgs; roots = [ base overridden ]; };
  disabledProject = agentLib.mkProject {
    inherit pkgs;
    name = "agent-environment-disabled";
    roots = [ (base.override { enableHarnesses = [ ]; }) ];
  };
}
