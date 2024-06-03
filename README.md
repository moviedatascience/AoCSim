# AoCSim
Simulation module for upcoming MMORPG Ashes of Creation


# Roadmap

### Todo

- Right side panel populates when user selects node
- Generate list of node names
- Apply list of names to nodes (Appears in side panel when user selects a node) ((thinking about just letting users type in node names -- Maybe dropdown?))
- Allow sieges to destroy nodes
- Assign Biome type to nodes
- Configure paths to pull from a config file instead of the script 
- Implement ZOI
- Implement node types (religious, economic, militristic, scientific etc)
- Add in Castle nodes
- Assign resources to nodes
- Allow GUI user to save and load different node boundaries
- Add housing to nodes
- Add seasons
- Add population to nodes
- Add four spawn points for population
- Allow Nodes to declare war with one another
- Add level marker to nodes
- Add shading of nodes based on population
- 


### Completed
- ~~Create SQLite DB~~
- ~~Create DB table for nodes~~
- ~~Create GUI for simulation~~
- ~~Create "start simulation" GUI button~~
- ~~Create "pause simulation" GUI button~~
- ~~Highlight node when cursor hovers within node boundaries (so much harder than I thought it would be)~~
- ~~Limit node progression based on surrounding nodes~~
- ~~Configure paths to pull from a config file instead of the script ~~
- ~~General settings put into collapsable left side panel ~~
- ~~Allow GUI user to move node boundaries ~~



# Brainstorming

What does the ideal usesr experience look like? 

The user launches the application from a shortcut they have pinned to their taskbar. They are prompted with two buttons "Resume" or "Create New". Resume is grayed out if there isn't a save file. User selects "Create New" and are provided two more choices. 1- "Create Map" and 2- "Edit Map Parameters" (unsure about what map parameters I would have but this is a placeholder for them). 


Once map is created they are provided two more choices. 1- "Simulation Mode" and 2- "Roleplay Mode"


1- "Start Simulation" 2- "Simulation Parameters" (simulation parameters would include things like speed, starting year, etc) 

Once the user starts the simulation 

