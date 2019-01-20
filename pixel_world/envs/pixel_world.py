import gym
from gym import error, spaces, utils
from gym.utils import seeding

import sys
import os 
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append('/'.join(dir_path.split('/')[:-1]))
sys.path.append(os.getcwd()+"\\pixel_world\\pixel_world\\")
from env_utils import *
import numpy as np

import matplotlib.pyplot as plt

class EnvReader(object):
    def __init__(self,source,source_type):
        self.memory = []
        self.source = source
        self.source_type = source_type

    def read(self):
        if self.source_type == 'file':
            f = open(self.source,"r")
            self.memory = [line.strip() for line in f.readlines()]
            f.close()
        else:
            self.memory = self.source.split('\n')
        return self.memory

    def close(self):
        self.memory = []
        
class PixelWorldSampler(object):
    def __init__(self,template_env):
        self.template = template_env
        self.map = self.template.text_map
        self.goal_symbol = -1
        self.agent_symbol = -1
        for symbol,d in self.template.reward_mapping.items():
            if 'initial' in d and 'terminal' in d:
                if d['initial'] or d['terminal']:
                    if d['initial']:
                        self.agent_symbol = symbol
                    if d['terminal']:
                        self.goal_symbol = symbol
                    for i,line in enumerate(self.map):
                        self.map[i] = line.replace(symbol,self.template.default_state)
        self.accessible_states = self.template.accessible_states
        
    def generate(self,train,train_split,test_split):
        assert train_split + test_split <= 100
        train_th = len(self.accessible_states) * (len(self.accessible_states)-1)
        rs = np.random.RandomState(0)
        idx = rs.permutation(list(range(train_th)))
        test_th = int(train_th *test_split/100)
        train_th = int(train_th * train_split/100)
        idx = idx[:train_th] if train else idx[train_th:train_th+test_th]
        k = 0
        acc = []
        for start_state in self.accessible_states:
            for goal_state in self.accessible_states:
                x_goal,y_goal = goal_state.coords
                x_start,y_start = start_state.coords
                if x_goal == x_start and y_goal == y_start:
                    continue
                k += 1
                new_map = np.array(self.map,copy=True)
                for i,line in enumerate(new_map):
                    for j,c in enumerate(line):
                        if x_goal == i and y_goal == j:
                            new_map[i] = new_map[i][:j] + self.goal_symbol + new_map[i][j+1:]
                        if x_start == i and y_start == j:
                            new_map[i] = new_map[i][:j] + self.agent_symbol + new_map[i][j+1:]
                acc.append('\n'.join(new_map))
        return np.array(acc)[idx] 

class PixelWorld(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self,reward_mapping,world_map="maps/room1.txt",default_state=' ',from_string=False):
        self.raw_map = []
        self.agent_color = reward_mapping['.agent']['color']
        self.initial_state = None
        self.goal_states = []
        self.default_state = default_state
        self.accessible_states = []
        self.reward_mapping = reward_mapping
        reader = EnvReader(source=world_map,source_type='str' if from_string else 'file')
        self.text_map = reader.read()
        reader.close()
        for i,line in enumerate(self.text_map):
            acc = []
            for j,s in enumerate(line):
                s = s if s in reward_mapping else self.default_state # if we see an unassigned state, make it default
                state = DiscreteState(**reward_mapping[s],coords=np.array([i,j]))
                acc.append(state)
                if reward_mapping[s]['terminal']:
                    self.goal_states.append(state)
                if state.initial: # Note that this overwrites multiple start states to the most recent one
                    self.initial_state = state
                if reward_mapping[s]['accessible']:
                    self.accessible_states.append(state)
            self.raw_map.append(acc)
        self.dim = (len(self.raw_map),len(self.raw_map[0]))
        self.current_state = self.initial_state
        self.action_vectors = np.array([[-1,0],[0,1],[1,0],[0,-1]])
        self.action_space = spaces.Discrete(4)
        self.observation_space = spaces.Box(low=0,high=255,shape=(3,self.dim[0],self.dim[1]),dtype=np.uint8)
        
    def _map2screen(self,transpose=False):
        pixel_map = []
        for i in range(self.dim[0]):
            acc = []
            for j in range(self.dim[1]):
                acc.append(self.raw_map[i][j].color if self.raw_map[i][j] != self.current_state else self.agent_color)
            pixel_map.append(acc)
        return np.array(pixel_map) if not transpose else np.array(pixel_map).transpose((2,0,1))
    
    def _action2vec(self,action):
        return self.action_vectors[action]
    
    def _project(self,state):
        i = max(0,min(self.dim[0],state[0])) # Find new (i,j) coordinates but without the agent falling
        j = max(0,min(self.dim[1],state[1]))
        next_state = self.raw_map[i][j] # If the state is not accessible (e.g. wall), return -1 and stay in place
        return next_state if next_state.accessible else -1

    def step(self, action):
        action = self._action2vec(action)
        next_state = self._project(self.current_state.coords + action)
        self.current_state = self.current_state if next_state == -1 else next_state
        reward = self.current_state.get_reward()
        return self._map2screen(True),reward,int(self.current_state.terminal),{} 
    
    def reset(self):
        self.current_state = self.initial_state
        return self._map2screen(True)
    
if __name__ == "__main__":
    env = PixelWorld(navigation_alphabet(),"../../maps/room1.txt")
    print(env.current_state.coords)
    env.step(0)
    env.reset()
    print(env.current_state.coords)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plot_screen(env,ax)