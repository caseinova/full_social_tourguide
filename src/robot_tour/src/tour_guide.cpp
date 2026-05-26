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
    sub_node_tour = rclcpp::Node::make_shared("subservient_tour_node");
    this->client_ptr_ = rclcpp_action::create_client<Waypoints>(
      this,
      "/follow_waypoints");
    subscription_ = this->create_subscription<std_msgs::msg::String>(
      "tour_command", 10, std::bind(&WaypointFollowerClient::topic_callback, this, std::placeholders::_1));
    this->tour_service_client_ = sub_node_tour->create_client<social_robot_interfaces::srv::Tours>("tour_retrieve");
    
  
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
    // rclcpp::shutdown();
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
    
    this->send_goal(result.get()->tour);
    RCLCPP_INFO(this->get_logger(), "goal sent");
  }
};  // class FibonacciActionClient

}  // namespace action_tutorials_cpp

RCLCPP_COMPONENTS_REGISTER_NODE(robot_tour::WaypointFollowerClient)