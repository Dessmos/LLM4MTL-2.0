grammar QVTO;

// ======================== Parser Rules ========================

compilationUnit
    : topLevelElement* EOF
    ;

topLevelElement
    : modeltypeDecl
    | transformationDecl
    | mainDecl
    | mappingDecl
    | constructorDecl
    ;

// --- modeltype ---
modeltypeDecl
    : 'modeltype' IDENTIFIER 'uses' StringLiteral ';'
    ;

// --- transformation ---
transformationDecl
    : 'transformation' IDENTIFIER '(' transformParamList ')' ';'
    ;

transformParamList
    : transformParam (',' transformParam)*
    ;

transformParam
    : direction IDENTIFIER ':' typeRef
    ;

direction
    : 'in' | 'out' | 'inout'
    ;

// --- main ---
mainDecl
    : 'main' '(' ')' block
    ;

// --- mapping ---
mappingDecl
    : 'abstract'? 'mapping' qualifiedName '::' IDENTIFIER
      '(' formalParamList? ')' ':' returnType
      mappingExtension* mappingBlock
    ;

returnType
    : typeRef ('@' IDENTIFIER)?
    ;

mappingExtension
    : 'inherits' mappingRef (',' mappingRef)*
    | 'merges'   mappingRef (',' mappingRef)*
    | 'disjuncts' mappingRef (',' mappingRef)*
    | 'when' '{' expression '}'
    ;

mappingRef
    : qualifiedName '::' IDENTIFIER
    ;

mappingBlock
    : '{' initSection? statement* '}'
    ;

initSection
    : 'init' block
    ;

// --- constructor ---
constructorDecl
    : 'constructor' qualifiedName '::' IDENTIFIER
      '(' formalParamList? ')' block
    ;

// --- shared ---
formalParamList
    : formalParam (',' formalParam)*
    ;

formalParam
    : IDENTIFIER ':' typeRef
    ;

typeRef
    : qualifiedName
    ;

qualifiedName
    : IDENTIFIER ('::' IDENTIFIER)*
    ;

block
    : '{' statement* '}'
    ;

// ======================== Statements ========================

statement
    : 'var' IDENTIFIER (':' typeRef)? ':=' expression ';'       # varDeclStmt
    | expression ((':=' | '+=') expression)? ';'                 # exprOrAssignStmt
    | 'if' expression 'then' block ('else' block)? 'endif' ';'  # ifStmt
    ;

// ======================== Expressions ========================

expression
    : orExpr
    ;

orExpr
    : andExpr ('or' andExpr)*
    ;

andExpr
    : notExpr ('and' notExpr)*
    ;

notExpr
    : 'not' notExpr
    | comparisonExpr
    ;

comparisonExpr
    : additiveExpr (('=' | '<>' | '<' | '>' | '<=' | '>=') additiveExpr)?
    ;

additiveExpr
    : callExpr (('+' | '-') callExpr)*
    ;

callExpr
    : primaryExpr suffix*
    ;

primaryExpr
    : 'self'
    | 'result'
    | 'null'
    | 'true'
    | 'false'
    | qualifiedName
    | StringLiteral
    | IntegerLiteral
    | 'new' typeRef '(' argumentList? ')'
    | 'object' typeRef ('@' IDENTIFIER)? objectBody
    | '(' expression ')'
    ;

suffix
    : '.' IDENTIFIER ('(' argumentList? ')')?        // .prop  or .method(args)
    | '->' IDENTIFIER ('(' argumentList? ')')?       // ->op() or ->prop
    | '->' 'map' IDENTIFIER ('(' argumentList? ')')? // ->map name(args)
    | '!' '[' typeRef ']'                             // ![Type] selectOne
    | '[' typeRef ']'                                 // [Type]  type filter
    ;

objectBody
    : '{' objectMember* '}'
    ;

objectMember
    : expression ((':=' | '+=') expression)? ';'?
    ;

argumentList
    : expression (',' expression)*
    ;

// ======================== Lexer Rules ========================

StringLiteral
    : '\'' (~['\r\n\\] | '\\' .)* '\''
    | '"'  (~["\r\n\\] | '\\' .)* '"'
    ;

IntegerLiteral
    : [0-9]+
    ;

IDENTIFIER
    : [a-zA-Z_] [a-zA-Z0-9_]*
    ;

WS
    : [ \t\r\n]+ -> skip
    ;

LINE_COMMENT
    : '--' ~[\r\n]* -> skip
    ;
