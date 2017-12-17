#Basic Python interface for the qhue system.... ip for bridge -> "192.168.0.2"
import qhue
import yaml
import phue
from os import path
from qhue import Bridge, QhueException, create_new_username 

#Setting Up Remote Access to Hue Bridge

def ManualLogin(LED_State, Desk_State, ip):
    
    """
    A way to manually login to the hue bridge, requires the button on the bridge to be pushed.
    Only useful should auto login fail.
    
    LES_State, Desk_State can either be True or False to test the lights
    
    ip for current bridge is 192.168.0.2
    
    """
    username = qhue.create_new_username(ip)
    #double check the user name - can be removed later
    print(username)
    
    b = qhue.Bridge(ip,username)
    
    b.lights[1].state(bri=250,hue=30000,on=LED_State)
    b.lights[4].state(bri=250,hue=10000,on=Desk_State) 
    
    return()
    
def Lights_Specs(SceneID):

    """
    Returns infomation about the chosen scene that has been created via the app. Useful for the 
    huetap device storing set scenes on the bridge.
    
    Scene ID can be found by b.scenes() if unknown.
    """       
    for num, info in lights.items():
        light_spec = print("{:16} {}".format(info['name'], num))
    
    s = b.scenes[SceneID]()
    
    scene_spec = print(yaml.safe_dump(s, indent=4))
    
    return(light_spec, scene_spec)

def main(Light_Function):
    
    """
    Creates a connection to the hue bridge and sets lights to desired setting.
    
    If a username has not been created, a new username is saved to a textfile which is then
    called for remote access. This must be done on site before remote access can be used.
    
    Light_Function = 1 to 6 with:
        
    1 = Observing
    2 = Observing Bright
    3 = Bright
    4 = All Lights On
    5 = All Lights Off
    6 = Flat Field
    """
    
    file_path = "hue_username.txt"
    
    ip = "192.168.0.2"
    
    if not path.exists(file_path):
        
        while True:
            try:
                username = create_new_username(ip)
                break
            except QhueException as err:
                print("Cannot create new username: {}".format(err))
                
                
        with open(file_path, "w") as cred_file:
            cred_file.write(username)
            print("Your hue username",username,"was created")
            
         
    else:
        
        with open(file_path, "r") as cred_file:
            username = cred_file.read()
            print("Login with username", username, "successful")
            
    b = Bridge(ip, username)
    
    if Light_Function == 1:         
        
       b.lights[1].state(bri=150, hue=250, sat = 20)
       b.lights[4].state(on = False)
       
       print("Observing Mode Selected")
       b.get_light(1, 'on')
       b.get_light(4, 'on')
       
    if Light_Function == 2:
        
       b.lights[1].state(bri=250, hue=200)
       b.lights[4].state(bri=250, hue = 2000)
       b.get_light(1, 'on')
       b.get_light(4, 'on')
        
       print("Observing Bright Mode Selected")
        
    if Light_Function == 3:
        
       b.lights[1].state(bri = 250, hue = 30000)
       b.lights[4].state(bri = 250, hue = 30000)
       b.get_light(1, 'on')
       b.get_light(4, 'on')
       
       print("Bright Mode Selected")
       
    if Light_Function == 4:
        
       b.lights[1].state(on = True)
       b.lights[4].state(on = True)
       b.get_light(1, 'on')
       b.get_light(4, 'on')
       
       print("All Lights On")
       
    if Light_Function == 5:
        
       b.lights[1].state(on = False)
       b.lights[4].state(on = False)
       b.get_light(1, 'on')
       b.get_light(4, 'on')
       
       print("All Lights Off")
    
    if Light_Function == 6:
        
       b.lights[1].state(on = False)
       b.lights[4].state(on = False)
       b.lights[5].state(on = True, bri = 250, hue = 30000, sat = 200) #New Flat Field Light
       b.get_light(1, 'on')
       b.get_light(4, 'on')
       b.get_light(5, 'on')
       
       print("Flat Field Mode Selected")
        
        
        
       
        
    
        
        
        

    
    
    
    















   
