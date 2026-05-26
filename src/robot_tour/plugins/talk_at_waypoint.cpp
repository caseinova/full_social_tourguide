// Copyright (c) 2026
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

#include "robot_tour/plugins/talk_at_waypoint.hpp"

#include <chrono>
#include <cstddef>
#include <stdexcept>
#include <string>

#include "nav2_util/node_utils.hpp"
#include "pluginlib/class_list_macros.hpp"

namespace robot_tour
{

TalkAtWaypoint::TalkAtWaypoint() = default;

void TalkAtWaypoint::initialize(
  const rclcpp_lifecycle::LifecycleNode::WeakPtr & parent,
  const std::string & plugin_name)
{
  auto node = parent.lock();
  if (!node) {
    throw std::runtime_error{"Failed to lock node in TalkAtWaypoint plugin"};
  }

  logger_ = node->get_logger();
  clock_ = node->get_clock();

  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".enabled", rclcpp::ParameterValue(true));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".waypoint_pause_duration", rclcpp::ParameterValue(0));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".talk_topic", rclcpp::ParameterValue(talk_topic_));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".waypoint_order_topic", rclcpp::ParameterValue(waypoint_order_topic_));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".default_message", rclcpp::ParameterValue(default_message_));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".waypoint_messages", rclcpp::ParameterValue(std::vector<std::string>{}));
  nav2_util::declare_parameter_if_not_declared(
    node, plugin_name + ".max_wait_duration", rclcpp::ParameterValue(30000));

  node->get_parameter(plugin_name + ".enabled", is_enabled_);
  node->get_parameter(plugin_name + ".waypoint_pause_duration", waypoint_pause_duration_);
  node->get_parameter(plugin_name + ".talk_topic", talk_topic_);
  node->get_parameter(plugin_name + ".waypoint_order_topic", waypoint_order_topic_);
  node->get_parameter(plugin_name + ".default_message", default_message_);
  node->get_parameter(plugin_name + ".waypoint_messages", waypoint_messages_);
  node->get_parameter(plugin_name + ".max_wait_duration", max_wait_duration_);
  if (waypoint_pause_duration_ < 0) {
    RCLCPP_WARN(
      logger_,
      "Negative waypoint_pause_duration was requested; using 0 milliseconds instead");
    waypoint_pause_duration_ = 0;
  }

  publisher_ = node->create_publisher<std_msgs::msg::String>(talk_topic_, rclcpp::SystemDefaultsQoS());
  done_talking_subscription_ = node->create_subscription<std_msgs::msg::String>("/done_talking", rclcpp::SystemDefaultsQoS(),std::bind(&TalkAtWaypoint::done_talking_callback_, this, std::placeholders::_1));
  auto waypoint_order_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
  waypoint_order_subscription_ = node->create_subscription<std_msgs::msg::Int64MultiArray>(
    waypoint_order_topic_,
    waypoint_order_qos,
    std::bind(&TalkAtWaypoint::waypoint_order_callback_, this, std::placeholders::_1));

  RCLCPP_INFO(
    logger_,
    "TalkAtWaypoint initialized: enabled=%s, talk_topic=%s, waypoint_order_topic=%s, pause=%d ms",
    is_enabled_ ? "true" : "false",
    talk_topic_.c_str(),
    waypoint_order_topic_.c_str(),
    waypoint_pause_duration_);
}

void TalkAtWaypoint::done_talking_callback_(const std_msgs::msg::String::ConstSharedPtr & msg)
{
  RCLCPP_INFO(logger_, "Received done talking signal: '%s'", msg->data.c_str());
  done_talking_flag_ = true;
}

void TalkAtWaypoint::waypoint_order_callback_(
  const std_msgs::msg::Int64MultiArray::ConstSharedPtr & msg)
{
  waypoint_order_ = msg->data;
  RCLCPP_INFO(logger_, "Received waypoint order map with %zu entries", waypoint_order_.size());
}

bool TalkAtWaypoint::processAtWaypoint(
  const geometry_msgs::msg::PoseStamped & /*curr_pose*/,
  const int & curr_waypoint_index)
{
  if (!is_enabled_) {
    return true;
  }

  auto talk_waypoint_index = curr_waypoint_index;
  if (
    curr_waypoint_index >= 0 &&
    static_cast<size_t>(curr_waypoint_index) < waypoint_order_.size())
  {
    talk_waypoint_index = static_cast<int>(waypoint_order_[curr_waypoint_index]);
  }

  std_msgs::msg::String msg;
  if (
    talk_waypoint_index >= 0 &&
    static_cast<size_t>(talk_waypoint_index) < waypoint_messages_.size() &&
    !waypoint_messages_[talk_waypoint_index].empty())
  {
    msg.data = waypoint_messages_[talk_waypoint_index];
  } else {
    msg.data = default_message_ + std::to_string(talk_waypoint_index);
  }

  publisher_->publish(msg);

  done_talking_flag_ = false;
  int wait_count_ = 0;

  RCLCPP_INFO(
    logger_,
    "Arrived at goal waypoint %d (tour waypoint %d), published talk command: '%s'",
    curr_waypoint_index,
    talk_waypoint_index,
    msg.data.c_str());
  
  while (wait_count_<=max_wait_duration_/waypoint_pause_duration_)
  {
      if (waypoint_pause_duration_ > 0) {
      clock_->sleep_for(std::chrono::milliseconds(waypoint_pause_duration_));
    }
    else {
      clock_->sleep_for(std::chrono::milliseconds(1000));
    }
    if(done_talking_flag_) {
      break;
    }
    wait_count_++;
  }
  RCLCPP_INFO(
      logger_,
      "Received done talking signal for tour waypoint %d, resuming navigation",
      talk_waypoint_index);

  return true;
}

}  // namespace robot_tour

PLUGINLIB_EXPORT_CLASS(robot_tour::TalkAtWaypoint, nav2_core::WaypointTaskExecutor)
