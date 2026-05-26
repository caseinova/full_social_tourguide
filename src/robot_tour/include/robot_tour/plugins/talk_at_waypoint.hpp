// Copyright (c) 2020 Fetullah Atas
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef ROBOT_TOUR__PLUGINS__TALK_AT_WAYPOINT_HPP_
#define ROBOT_TOUR__PLUGINS__TALK_AT_WAYPOINT_HPP_
#pragma once

#include <string>
#include <vector>

#include "nav2_core/waypoint_task_executor.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "std_msgs/msg/string.hpp"

namespace robot_tour
{

/**
 * @brief WaypointTaskExecutor plugin that publishes a talk command when a
 * waypoint is reached, then optionally pauses before Nav2 continues.
 */
class TalkAtWaypoint : public nav2_core::WaypointTaskExecutor
{
public:
  TalkAtWaypoint();

  ~TalkAtWaypoint() override = default;

  void initialize(
    const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
    const std::string & plugin_name) override;


  bool processAtWaypoint(
    const geometry_msgs::msg::PoseStamped & curr_pose,
    const int & curr_waypoint_index) override;

protected:
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr done_talking_subscription_;
  void done_talking_callback_(const std_msgs::msg::String::ConstSharedPtr & msg);
  int waypoint_pause_duration_{200};
  int max_wait_duration_{30000};
  bool is_enabled_{true};
  std::string talk_topic_{"/talk_command"};
  std::string default_message_{"Arrived at waypoint "};
  std::vector<std::string> waypoint_messages_;
  rclcpp::Logger logger_{rclcpp::get_logger("robot_tour")};
  rclcpp::Clock::SharedPtr clock_;
  bool done_talking_flag_{false};
};

}  // namespace robot_tour
#endif  // ROBOT_TOUR__PLUGINS__TALK_AT_WAYPOINT_HPP_
