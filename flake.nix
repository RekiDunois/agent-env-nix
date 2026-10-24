{
  description = "Small producer-owned Nix packages with safe project-local Codex activation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/6510408d147d8c5e6d76043e899e9251756f6a75";
    agent-skills = {
      url = "github:Kyure-A/agent-skills-nix/2948865044b2af55c8c4e4eb2abda7de79d60f0e";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    mcp-servers = {
      url = "github:natsukium/mcp-servers-nix/31848978eefbca17f1658a55066b1d2aaa43cafc";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ self, nixpkgs, ... }:
    let
      lib = nixpkgs.lib;
      systems = [ "x86_64-linux" "aarch64-darwin" ];
      eachSystem = lib.genAttrs systems;
      agentLib = import ./lib {
        inherit lib;
        agentSkills = inputs.agent-skills;
        mcpServers = inputs.mcp-servers;
      };
      examples = eachSystem (system: import ./examples {
        pkgs = nixpkgs.legacyPackages.${system};
        inherit agentLib;
      });
    in
    {
      lib = agentLib;
      packages = eachSystem (system: {
        default = examples.${system}.project;
        example = examples.${system}.project;
        example-dsh = examples.${system}.dshProject;
        example-disabled = examples.${system}.disabledProject;
      });
      apps = eachSystem (system: {
        default = { type = "app"; program = "${self.packages.${system}.default}/bin/agent-env"; };
      });
      checks = eachSystem (system: import ./tests {
        pkgs = nixpkgs.legacyPackages.${system};
        inherit agentLib;
        example = examples.${system};
      });
      devShells = eachSystem (system: {
        default = nixpkgs.legacyPackages.${system}.mkShell {
          packages = [ (nixpkgs.legacyPackages.${system}.python3.withPackages (ps: [ ps.tomlkit ])) ];
        };
      });
      formatter = eachSystem (system: nixpkgs.legacyPackages.${system}.nixfmt);
    };
}

