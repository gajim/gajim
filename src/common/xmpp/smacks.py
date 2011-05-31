from protocol import Acks
from protocol import NS_STREAM_MGMT

class Smacks():
    '''
    This is Smacks is the Stream Management class. It takes care of requesting
    and sending acks. Also, it keeps track of the unhandled outgoing stanzas.
    
    The dispatcher has to be able to access this class to increment the 
    number of handled stanzas
    '''


    def __init__(self, owner):
        self._owner = owner
        self.out_h = 0 # Outgoing stanzas handled
        self.in_h = 0  # Incoming stanzas handled
        self.uqueue = [] # Unhandled stanzas queue
        
        #Register handlers 
        owner.Dispatcher.RegisterNamespace(NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('enabled', self._neg_response
                                         ,xmlns=NS_STREAM_MGMT)
        owner.Dispatcher.RegisterHandler('r', self.send_ack
                                         ,xmlns=NS_STREAM_MGMT)

        
    def negociate(self):
        stanza = Acks()
        stanza.buildEnable()
        self._owner.Connection.send(stanza, True)
        
    def _neg_response(self, disp, stanza):
        pass
    
    def send_ack(self, disp, stanza):
        ack = Acks()
        ack.buildAnswer(self.in_h)
        self._owner.Connection.send(ack, False)
        
    def request_ack(self):
        r = Acks()
        r.buildRequest()
        self._owner.Connection.send(r, False)