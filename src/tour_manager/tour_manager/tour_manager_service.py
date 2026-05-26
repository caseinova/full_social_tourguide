from social_robot_interfaces.srv import Tours, Description

from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import rclpy
from rclpy.node import Node
import sqlite3
from json import dumps, loads

class TourManager(Node):

    def __init__(self):
        super().__init__('tour_manager')
        self.get_logger().info('Initializing tour manager')
        self.declare_parameter('tour_description_default', 'Placeholder name |No description provided')
        self.default_description_ = self.get_parameter('tour_description_default').get_parameter_value().string_value
        self.srv = self.create_service(Tours, 'tour_retrieve', self.tour_retrieve_callback)
        self.get_description_ = self.create_service(Description, 'retrieve_description', self.retrieve_description_callback)
        self.subscription_ = self.create_subscription(PoseStamped,'save_tour',self.save_tour_callback,10)
        self.con = sqlite3.connect("tours.db")
        cur = self.con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS tours (px,py,pz,qx,qy,qz,qw,description)")
        columns = [column[1] for column in cur.execute("PRAGMA table_info(tours)").fetchall()]
        if 'description' not in columns:
            cur.execute("ALTER TABLE tours ADD COLUMN description TEXT")
            cur.execute("UPDATE tours SET description = ? WHERE description IS NULL", (self.default_description_,))
            self.con.commit()

    def tour_retrieve_callback(self, request, response):
        tour_obj = self.retrieve_tour(request.idx)
        # print(tour_obj)
        # self.get_logger().info('Incoming request: retrieving tour number %d',request.idx)
        
        list_=[]
        k=0
        # print(len(tour_obj))
        # print(tour_obj)
        for i in tour_obj:
            k+=1
            waypoint = PoseStamped()
            waypoint.header.frame_id = "map"
            waypoint.pose.position.x = i[0]
            waypoint.pose.position.y = i[1]
            waypoint.pose.position.z = i[2]
            waypoint.pose.orientation.x = i[3]
            waypoint.pose.orientation.y = i[4]
            waypoint.pose.orientation.z = i[5]
            waypoint.pose.orientation.w = i[6]
            list_.append(waypoint)
            print(f'goal {k} is {i[0]}, {i[1]}')
        print(list_)
        response.tour=list_
        return response
    
    def retrieve_description_callback(self, request, response):
        tour_obj = self.retrieve_tour(0)
        try:
            if request.idx < 0:
                raise IndexError
            description = tour_obj[request.idx][7]
            if description is None:
                description = self.default_description_
            response.description = String(data=description)
        except (IndexError, TypeError):
            response.description = String(data="Invalid tour index")
        
        return response
    
    def save_tour_callback(self, msg):
        self.add_point(msg)
    
    def add_point(self, x: PoseStamped):
        cur = self.con.cursor()
        cur.execute(
            "INSERT INTO tours (px,py,pz,qx,qy,qz,qw,description) VALUES (?,?,?,?,?,?,?,?)",
            (x.pose.position.x,x.pose.position.y,x.pose.position.z,x.pose.orientation.x,x.pose.orientation.y,x.pose.orientation.z,x.pose.orientation.w,self.default_description_))
        self.con.commit()
        self.get_logger().info('Saved 1 new waypoint into tour')


    def retrieve_tour(self, idx):
        cur = self.con.cursor()
        # print(idx)
        res = cur.execute("SELECT * FROM tours")
        # json_obj = loads(res.fetchone()[0])
        # res = cur.execute("SELECT * FROM tours")
        # if (res.fetchone() is None):
        #     return None
        # else:
        #     json_obj = loads(res.fetchone())
        # print(res.fetchall())
        return res.fetchall()
        




def main(args=None):
    rclpy.init(args=args)

    tour_manager = TourManager()

    rclpy.spin(tour_manager)

    rclpy.shutdown()
    tour_manager.con.close()


if __name__ == '__main__':
    main()
