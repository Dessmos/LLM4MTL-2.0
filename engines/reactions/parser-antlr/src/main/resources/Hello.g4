grammar Hello;

r: 'Hello' NAME | t ;
t: 'Goodbye' NAME;
NAME: [a-zA-Z]+;
WS: [ \t\r\n]+ -> skip;