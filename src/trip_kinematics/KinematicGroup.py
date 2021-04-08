from typing import Dict, List, Callable
from trip_kinematics.KinematicChainPart import KinematicChainPart


class KinematicGroup(KinematicChainPart):

    def __init__(self, name: str, open_chain: List[KinematicChainPart], initial_state: Dict[str, float], f_mapping: Callable, g_mapping: Callable, parent: KinematicChainPart = None) -> None:
        super().__init__(name, parent)
        self.__open_chain = open_chain
        self.__state = initial_state
        self.virtual_state = []

        # Sort
        sorted_open_chain = []

        for part in open_chain:
            if part.get_parent() == None:
                sorted_open_chain.append(part)

        if len(sorted_open_chain) > 1:
            raise RuntimeError("To many loose ends inside group.")

        buffer = sorted_open_chain[0]

        while buffer.get_child() != None:
            sorted_open_chain.append(buffer)
            buffer = buffer.get_child()

        for part in sorted_open_chain:
            self.virtual_state.append(part.get_state())

        self.__f_mapping = f_mapping
        self.__g_mapping = g_mapping

        # ToDo: Check mapping

    def set_state(self, dir, state: Dict[str, float]) -> None:

        if self.__state.keys() == state.keys():
            self.__state = state
            self.__virtual_state = self.__f_mapping(self.__state)

        elif map(lambda obj: obj.keys(), self.__virtual_state) == map(lambda obj: obj.keys(), state):
            self.__virtual_state = state
            self.__state = self.__g_mapping(self.__virtual_state)

    def get_state(self) -> List[Dict[str, float]]:
        return self.__virtual_state
