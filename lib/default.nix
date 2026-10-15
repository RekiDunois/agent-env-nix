{ lib, agentSkills, mcpServers }:
let
  normalizeMcp = import ./mcp.nix { inherit lib; };
  mkAgentPackage = lib.makeOverridable (import ./package.nix {
    inherit lib mcpServers normalizeMcp;
  });
  mkProject = lib.makeOverridable (import ./project.nix {
    inherit lib agentSkills mcpServers;
  });
in
{
  inherit mkAgentPackage mkProject;
}
