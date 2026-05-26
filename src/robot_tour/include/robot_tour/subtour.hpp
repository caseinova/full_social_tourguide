#ifndef ROBOT_TOUR__SUBTOUR_HPP_
#define ROBOT_TOUR__SUBTOUR_HPP_

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"
#include "geometry_msgs/msg/pose_stamped.hpp"
#include "nav2_msgs/action/follow_waypoints.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "social_robot_interfaces/msg/tsp_command.hpp"
#include "social_robot_interfaces/srv/tours.hpp"
#include "std_msgs/msg/string.hpp"

namespace robot_tour
{
    class SubtourNode : public rclcpp::Node
    {
        public:
        using Waypoints = nav2_msgs::action::FollowWaypoints;
        using GoalHandleWaypoints = rclcpp_action::ClientGoalHandle<Waypoints>;

        explicit SubtourNode(const rclcpp::NodeOptions & options);
        ~SubtourNode() override = default;

        float computeCost(
            const geometry_msgs::msg::PoseStamped &,
            const geometry_msgs::msg::PoseStamped &);
        float getCost(int, int);
        int getClosestNodeIdx(int, const std::vector<int> &);
        bool makeCostMatrix(const std::vector<geometry_msgs::msg::PoseStamped> &);
        bool initializeTour(int start_node_idx);
        float computeTourCost(void);
        bool improveTour(int);

        private:
        void tspCommandCallback(const social_robot_interfaces::msg::TspCommand::SharedPtr msg);
        void currentPoseCallback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg);
        void tourResponseCallback(
            const std::vector<int64_t> & waypoint_indices,
            rclcpp::Client<social_robot_interfaces::srv::Tours>::SharedFuture future);
        int getStartNodeIdx(const std::vector<geometry_msgs::msg::PoseStamped> & poses);
        std::vector<geometry_msgs::msg::PoseStamped> solveTour(
            const std::vector<geometry_msgs::msg::PoseStamped> & poses,
            int max_iterations);
        void sendGoal(const std::vector<geometry_msgs::msg::PoseStamped> & poses);
        void goalResponseCallback(const GoalHandleWaypoints::SharedPtr & goal_handle);
        void feedbackCallback(
            GoalHandleWaypoints::SharedPtr,
            const std::shared_ptr<const Waypoints::Feedback> feedback);
        void resultCallback(const GoalHandleWaypoints::WrappedResult & result);
        void publishDockCommand();

        rclcpp::Subscription<social_robot_interfaces::msg::TspCommand>::SharedPtr tsp_subscription_;
        rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr current_pose_subscription_;
        rclcpp::Publisher<std_msgs::msg::String>::SharedPtr dock_command_publisher_;
        rclcpp_action::Client<Waypoints>::SharedPtr waypoint_client_;
        rclcpp::Client<social_robot_interfaces::srv::Tours>::SharedPtr tour_service_client_;
        int max_2opt_iterations_ = 1000;
        bool dock_after_tour_ = false;
        bool has_current_pose_ = false;
        geometry_msgs::msg::PoseStamped current_pose_;

        std::vector<std::vector<float>> cost_matrix;
        std::vector<int> current_tour;
        int num_nodes = 0;

        static constexpr float large_number = 9999999.0F;
    };
}  // namespace robot_tour

#endif  // ROBOT_TOUR__SUBTOUR_HPP_
