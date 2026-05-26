import os
import sys
import json
import glob
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess

# Define structural relative paths matching package asset layouts
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: Adjust 'tablet_assets' base workspace paths if it sits outside this subfolder
TABLET_ASSETS_DIR = os.path.join(PACKAGE_DIR, 'tablet_assets')

def generate_launch_description():
    explanation_dir = os.path.join(TABLET_ASSETS_DIR, 'exhibition_explanation')
    images_dir = os.path.join(TABLET_ASSETS_DIR, 'exhibition_images')
    manifest_out_path = os.path.join(TABLET_ASSETS_DIR, 'exhibition_commands.json')

    # Basic directory verification guardrails
    if not os.path.exists(explanation_dir):
        print(f"\n[BOOTUP ERROR] The target directory '{explanation_dir}' does not exist.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # PART 1: DYNAMIC PARSING & ERROR CHECKING FOR MANIFEST GENERATION
    # -------------------------------------------------------------------------
    manifest_data = {}
    found_indexes = {}
    txt_files = glob.glob(os.path.join(explanation_dir, '*.txt'))

    for file_path in sorted(txt_files):
        filename = os.path.basename(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                continue # Skip empty config nodes safely
                
            # Parse the text data fields delimited by "|"
            parts = content.split('|')
            if len(parts) < 2:
                print(f"\n[BOOTUP ERROR] File '{filename}' is improperly formatted. Expected '[index]|[title]|[explanation]'.")
                sys.exit(1)
                
            try:
                idx = int(parts[0].strip())
            except ValueError:
                print(f"\n[BOOTUP ERROR] File '{filename}' contains an invalid non-integer index: '{parts[0]}'")
                sys.exit(1)
                
            raw_title = parts[1].strip()
            # Generate a clean, lowercase key safe for dictionary structures and ROS matches
            json_key = raw_title.lower().replace(' ', '_')

            # CRITICAL CHECK 1: Duplicate Index Collisions
            if idx in found_indexes:
                print(f"\n[BOOTUP ERROR] Duplicate index collision detected! Index {idx} is claimed by both:")
                print(f"  - {found_indexes[idx]}")
                print(f"  - {filename}")
                sys.exit(1)
                
            found_indexes[idx] = filename

            # Resolve matching directory frames by tracking matching titles
            matching_img_folder = os.path.join(images_dir, json_key)
            # Fallback path if the image folder utilizes an alternative variation layout (e.g. double_pendulum vs glowing_double_pendulum)
            if not os.path.exists(matching_img_folder):
                # Search for any loose sub-directory keyword matches if strict name matching fails
                subdirs = [d for d in os.listdir(images_dir) if os.path.isdir(os.path.join(images_dir, d))]
                matched_sub = next((s for s in subdirs if s in json_key or json_key in s), json_key)
                rel_image_path = os.path.join('exhibition_images', matched_sub)
            else:
                rel_image_path = os.path.join('exhibition_images', json_key)

            # Build JSON row elements keeping tracks relative to server asset configurations
            manifest_data[json_key] = {
                "id": idx,  # Embed parsed index number parameters
                "label": raw_title,
                "text_file": os.path.join('exhibition_explanation', filename),
                "image_folder": rel_image_path
            }

        except Exception as e:
            print(f"\n[BOOTUP ERROR] Failed processing {filename}: {str(e)}")
            sys.exit(1)

    # CRITICAL CHECK 2: Sequence Gaps / Missing Index Verification
    if found_indexes:
        min_idx = min(found_indexes.keys())
        max_idx = max(found_indexes.keys())
        
        # Verify strict structural sequences from lowest to highest indices
        for i in range(min_idx, max_idx + 1):
            if i not in found_indexes:
                print(f"\n[BOOTUP ERROR] Index Sequence Discontinuity! Index number {i} was skipped entirely.")
                print(f"Available Map Tracking Layout: {sorted(found_indexes.items())}")
                sys.exit(1)

    # Output verified JSON configuration datasets straight to filesystems
    try:
        with open(manifest_out_path, 'w', encoding='utf-8') as json_file:
            json.dump(manifest_data, json_file, indent=4)
        print(f"\n[BOOTUP SUCCESS] Dynamically synchronized and wrote '{manifest_out_path}' cleanly.")
    except Exception as e:
        print(f"\n[BOOTUP ERROR] Could not write manifest file updates: {str(e)}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # PART 2: GENERATE THE ROS 2 ACTION GRAPH RUNTIME
    # -------------------------------------------------------------------------
    ld = LaunchDescription()

    # Append standard binary executor Nodes
    ld.add_action(Node(
        package='pepper_hri',
        executable='tablet_builder',
        output='screen',
        name='tablet_builder_node'
    ))
    
    ld.add_action(Node(
        package='pepper_hri',
        executable='hri_coordinator',
        output='screen',
        name='hri_coordinator_node'
    ))
    
    ld.add_action(Node(
        package='pepper_hri',
        executable='gesture_manager',
        output='screen',
        name='pepper_gesture_node'
    ))

    # PART 3: PUBLISH INDIVIDUAL TEXT FILES TO THE /save_tour_command TOPIC
    # Loops through the files verified in Part 1 and deploys independent shell execution calls
    for file_path in txt_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_file_content = f.read().strip()
            
            if not raw_file_content:
                continue

            # Escape quotes cleanly to pass through standard shell executions safely
            escaped_payload = raw_file_content.replace("'", "'\\''")

            # Execute a standalone terminal action package to broadcast parameters
            # UNCOMMENT WHEN CONFIRMING WHERE TO SEND .TXT FILES
"""             publish_action = ExecuteProcess(
                cmd=[
                    'ros2', 'topic', 'pub', '--once', 
                    '/save_tour_command', 'std_msgs/String', 
                    f"data: '{escaped_payload}'"
                ],
                output='screen'
            )
            ld.add_action(publish_action) """
            
        except Exception as e:
            print(f"[LAUNCH WARNING] Could not register push publisher tasks for {file_path}: {e}")

    return ld