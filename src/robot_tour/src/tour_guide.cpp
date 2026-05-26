#include <functional>
#include <future>
#include <memory>
#include <string>
#include <sstream>

#include "nav2_msgs/action/follow_waypoints.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "rclcpp_components/register_node_macro.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "std_msgs/msg/int64_multi_array.hpp"
#include "std_msgs/msg/string.hpp"
#include "social_robot_interfaces/srv/tours.hpp"

namespace robot_tour
{
class WaypointFollowerClient : public rclcpp::Node
{
public:
  using Waypoints = nav2_msgs::action::FollowWaypoints;
  using GoalHandleWaypoints = rclcpp_action::ClientGoalHandle<Waypoints>;

  explicit WaypointFollowerClient(const rclcpp::NodeOptions & options)
  : Node("waypoint_action_client", options)
  {
    dock_after_tour_ = this->declare_parameter<bool>("dock_after_tour", false);
    const auto dock_command_topic = this->declare_parameter<std::string>(
      "dock_command_topic", "/dock_command");
    const auto waypoint_order_topic = this->declare_parameter<std::string>(
      "waypoint_order_topic", "/tour_waypoint_order");

    sub_node_tour = rclcpp::Node::make_shared("subservient_tour_node");
    this->client_ptr_ = rclcpp_action::create_client<Waypoints>(
      this,
      "/follow_waypoints");
    subscription_ = this->create_subscription<std_msgs::msg::String>(
      "tour_command", 10, std::bind(&WaypointFollowerClient::topic_callback, this, std::placeholders::_1));
    dock_command_publisher_ = this->create_publisher<std_msgs::msg::String>(dock_command_topic, 10);
    auto waypoint_order_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
    waypoint_order_publisher_ = this->create_publisher<std_msgs::msg::Int64MultiArray>(
      waypoint_order_topic,
      waypoint_order_qos);
    this->tour_service_client_ = sub_node_tour->create_client<social_robot_interfaces::srv::Tours>("tour_retrieve");
    RCLCPP_INFO(
      this->get_logger(),
      "Tour guide dock_after_tour=%s, dock_command_topic='%s', waypoint_order_topic='%s'",
      dock_after_tour_ ? "true" : "false",
      dock_command_topic.c_str(),
      waypoint_order_topic.c_str());
    
  
  }

  void send_goal(std::vector<geometry_msgs::msg::PoseStamped> poses)
  {
    using namespace std::placeholders;


    if (!this->client_ptr_->wait_for_action_server()) {
      RCLCPP_ERROR(this->get_logger(), "Action server not available after waiting");
      rclcpp::shutdown();
    }

    auto goal_msg = Waypoints::Goal();
    goal_msg.poses = poses;

    RCLCPP_INFO(this->get_logger(), "Sending goal");

    auto send_goal_options = rclcpp_action::Client<Waypoints>::SendGoalOptions();
    send_goal_options.goal_response_callback =
      std::bind(&WaypointFollowerClient::goal_response_callback, this, _1);
    send_goal_options.feedback_callback =
      std::bind(&WaypointFollowerClient::feedback_callback, this, _1, _2);
    send_goal_options.result_callback =
      std::bind(&WaypointFollowerClient::result_callback, this, _1);
    this->client_ptr_->async_send_goal(goal_msg, send_goal_options);
  }

private:
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
  rclcpp_action::Client<Waypoints>::SharedPtr client_ptr_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::shared_ptr<rclcpp::Node> sub_node_tour;
  rclcpp::Client<social_robot_interfaces::srv::Tours>::SharedPtr tour_service_client_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr dock_command_publisher_;
  rclcpp::Publisher<std_msgs::msg::Int64MultiArray>::SharedPtr waypoint_order_publisher_;
  bool dock_after_tour_ = false;

  void goal_response_callback(std::shared_ptr<GoalHandleWaypoints> future)
  {
    auto goal_handle = future.get();
    if (!goal_handle) {
      RCLCPP_ERROR(this->get_logger(), "Goal was rejected by server");
    } else {
      RCLCPP_INFO(this->get_logger(), "Goal accepted by server, waiting for result");
    }
  }

  void feedback_callback(
    GoalHandleWaypoints::SharedPtr,
    const std::shared_ptr<const Waypoints::Feedback> feedback)
  {

    RCLCPP_INFO(this->get_logger(), "The current goal is %d", feedback->current_waypoint);
  }

  void result_callback(const GoalHandleWaypoints::WrappedResult & result)
  {
    switch (result.code) {
      case rclcpp_action::ResultCode::SUCCEEDED:
        break;
      case rclcpp_action::ResultCode::ABORTED:
        RCLCPP_ERROR(this->get_logger(), "Goal was aborted");
        return;
      case rclcpp_action::ResultCode::CANCELED:
        RCLCPP_ERROR(this->get_logger(), "Goal was canceled");
        return;
      default:
        RCLCPP_ERROR(this->get_logger(), "Unknown result code");
        return;
    }

    for (long unsigned int i=0;i<size(result.result->missed_waypoints);i++)
    {
    RCLCPP_INFO(this->get_logger(), "Missed %u \n", result.result->missed_waypoints[i]);
    }
    publish_dock_command();
    // rclcpp::shutdown();
  }

  void publish_dock_command()
  {
    this->get_parameter("dock_after_tour", dock_after_tour_);
    if (!dock_after_tour_) {
      RCLCPP_INFO(this->get_logger(), "dock_after_tour is false; not publishing dock command");
      return;
    }

    auto msg = std_msgs::msg::String();
    msg.data = "dock";
    dock_command_publisher_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "Published dock command after tour completion");
  }

  void publish_waypoint_order(std::size_t waypoint_count)
  {
    auto msg = std_msgs::msg::Int64MultiArray();
    msg.data.reserve(waypoint_count);
    for (std::size_t i = 0; i < waypoint_count; ++i) {
      msg.data.push_back(static_cast<int64_t>(i));
    }

    waypoint_order_publisher_->publish(msg);
    RCLCPP_INFO(this->get_logger(), "Published waypoint order map with %zu entries", msg.data.size());
  }

  void topic_callback(const std_msgs::msg::String::SharedPtr msg)
  {
    RCLCPP_INFO(this->get_logger(), "received %s", msg->data.c_str());
    auto request = std::make_shared<social_robot_interfaces::srv::Tours::Request>();
    request->idx = 0;

    while (!this->tour_service_client_->wait_for_service(std::chrono::seconds(1))) {
      if (!rclcpp::ok()) {
        RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Interrupted while waiting for the service. Exiting.");
        return;
      }
      RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "service not available, waiting again...");
    }

    auto result = this->tour_service_client_->async_send_request(request);

    if (rclcpp::spin_until_future_complete(this->sub_node_tour, result) ==
      rclcpp::FutureReturnCode::SUCCESS)
    {
      RCLCPP_INFO(rclcpp::get_logger("rclcpp"), "Success");
    } else {
      RCLCPP_ERROR(rclcpp::get_logger("rclcpp"), "Failed");
    }
    
    const auto tour = result.get()->tour;
    publish_waypoint_order(tour.size());
    this->send_goal(tour);
    RCLCPP_INFO(this->get_logger(), "goal sent");
  }
};  // class FibonacciActionClient

}  // namespace action_tutorials_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(robot_tour::WaypointFollowerClient)
