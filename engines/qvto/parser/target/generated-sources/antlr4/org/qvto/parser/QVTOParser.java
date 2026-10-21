// Generated from org/qvto/parser/QVTO.g4 by ANTLR 4.13.1
package org.qvto.parser;
import org.antlr.v4.runtime.atn.*;
import org.antlr.v4.runtime.dfa.DFA;
import org.antlr.v4.runtime.*;
import org.antlr.v4.runtime.misc.*;
import org.antlr.v4.runtime.tree.*;
import java.util.List;
import java.util.Iterator;
import java.util.ArrayList;

@SuppressWarnings({"all", "warnings", "unchecked", "unused", "cast", "CheckReturnValue"})
public class QVTOParser extends Parser {
	static { RuntimeMetaData.checkVersion("4.13.1", RuntimeMetaData.VERSION); }

	protected static final DFA[] _decisionToDFA;
	protected static final PredictionContextCache _sharedContextCache =
		new PredictionContextCache();
	public static final int
		T__0=1, T__1=2, T__2=3, T__3=4, T__4=5, T__5=6, T__6=7, T__7=8, T__8=9, 
		T__9=10, T__10=11, T__11=12, T__12=13, T__13=14, T__14=15, T__15=16, T__16=17, 
		T__17=18, T__18=19, T__19=20, T__20=21, T__21=22, T__22=23, T__23=24, 
		T__24=25, T__25=26, T__26=27, T__27=28, T__28=29, T__29=30, T__30=31, 
		T__31=32, T__32=33, T__33=34, T__34=35, T__35=36, T__36=37, T__37=38, 
		T__38=39, T__39=40, T__40=41, T__41=42, T__42=43, T__43=44, T__44=45, 
		T__45=46, T__46=47, T__47=48, T__48=49, T__49=50, T__50=51, T__51=52, 
		T__52=53, T__53=54, T__54=55, StringLiteral=56, IntegerLiteral=57, IDENTIFIER=58, 
		WS=59, LINE_COMMENT=60;
	public static final int
		RULE_compilationUnit = 0, RULE_topLevelElement = 1, RULE_modeltypeDecl = 2, 
		RULE_transformationDecl = 3, RULE_transformParamList = 4, RULE_transformParam = 5, 
		RULE_direction = 6, RULE_mainDecl = 7, RULE_mappingDecl = 8, RULE_returnType = 9, 
		RULE_mappingExtension = 10, RULE_mappingRef = 11, RULE_mappingBlock = 12, 
		RULE_initSection = 13, RULE_constructorDecl = 14, RULE_formalParamList = 15, 
		RULE_formalParam = 16, RULE_typeRef = 17, RULE_qualifiedName = 18, RULE_block = 19, 
		RULE_statement = 20, RULE_expression = 21, RULE_orExpr = 22, RULE_andExpr = 23, 
		RULE_notExpr = 24, RULE_comparisonExpr = 25, RULE_additiveExpr = 26, RULE_callExpr = 27, 
		RULE_primaryExpr = 28, RULE_suffix = 29, RULE_objectBody = 30, RULE_objectMember = 31, 
		RULE_argumentList = 32;
	private static String[] makeRuleNames() {
		return new String[] {
			"compilationUnit", "topLevelElement", "modeltypeDecl", "transformationDecl", 
			"transformParamList", "transformParam", "direction", "mainDecl", "mappingDecl", 
			"returnType", "mappingExtension", "mappingRef", "mappingBlock", "initSection", 
			"constructorDecl", "formalParamList", "formalParam", "typeRef", "qualifiedName", 
			"block", "statement", "expression", "orExpr", "andExpr", "notExpr", "comparisonExpr", 
			"additiveExpr", "callExpr", "primaryExpr", "suffix", "objectBody", "objectMember", 
			"argumentList"
		};
	}
	public static final String[] ruleNames = makeRuleNames();

	private static String[] makeLiteralNames() {
		return new String[] {
			null, "'modeltype'", "'uses'", "';'", "'transformation'", "'('", "')'", 
			"','", "':'", "'in'", "'out'", "'inout'", "'main'", "'abstract'", "'mapping'", 
			"'::'", "'@'", "'inherits'", "'merges'", "'disjuncts'", "'when'", "'{'", 
			"'}'", "'init'", "'constructor'", "'var'", "':='", "'+='", "'if'", "'then'", 
			"'else'", "'endif'", "'or'", "'and'", "'not'", "'='", "'<>'", "'<'", 
			"'>'", "'<='", "'>='", "'+'", "'-'", "'self'", "'result'", "'null'", 
			"'true'", "'false'", "'new'", "'object'", "'.'", "'->'", "'map'", "'!'", 
			"'['", "']'"
		};
	}
	private static final String[] _LITERAL_NAMES = makeLiteralNames();
	private static String[] makeSymbolicNames() {
		return new String[] {
			null, null, null, null, null, null, null, null, null, null, null, null, 
			null, null, null, null, null, null, null, null, null, null, null, null, 
			null, null, null, null, null, null, null, null, null, null, null, null, 
			null, null, null, null, null, null, null, null, null, null, null, null, 
			null, null, null, null, null, null, null, null, "StringLiteral", "IntegerLiteral", 
			"IDENTIFIER", "WS", "LINE_COMMENT"
		};
	}
	private static final String[] _SYMBOLIC_NAMES = makeSymbolicNames();
	public static final Vocabulary VOCABULARY = new VocabularyImpl(_LITERAL_NAMES, _SYMBOLIC_NAMES);

	/**
	 * @deprecated Use {@link #VOCABULARY} instead.
	 */
	@Deprecated
	public static final String[] tokenNames;
	static {
		tokenNames = new String[_SYMBOLIC_NAMES.length];
		for (int i = 0; i < tokenNames.length; i++) {
			tokenNames[i] = VOCABULARY.getLiteralName(i);
			if (tokenNames[i] == null) {
				tokenNames[i] = VOCABULARY.getSymbolicName(i);
			}

			if (tokenNames[i] == null) {
				tokenNames[i] = "<INVALID>";
			}
		}
	}

	@Override
	@Deprecated
	public String[] getTokenNames() {
		return tokenNames;
	}

	@Override

	public Vocabulary getVocabulary() {
		return VOCABULARY;
	}

	@Override
	public String getGrammarFileName() { return "QVTO.g4"; }

	@Override
	public String[] getRuleNames() { return ruleNames; }

	@Override
	public String getSerializedATN() { return _serializedATN; }

	@Override
	public ATN getATN() { return _ATN; }

	public QVTOParser(TokenStream input) {
		super(input);
		_interp = new ParserATNSimulator(this,_ATN,_decisionToDFA,_sharedContextCache);
	}

	@SuppressWarnings("CheckReturnValue")
	public static class CompilationUnitContext extends ParserRuleContext {
		public TerminalNode EOF() { return getToken(QVTOParser.EOF, 0); }
		public List<TopLevelElementContext> topLevelElement() {
			return getRuleContexts(TopLevelElementContext.class);
		}
		public TopLevelElementContext topLevelElement(int i) {
			return getRuleContext(TopLevelElementContext.class,i);
		}
		public CompilationUnitContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_compilationUnit; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterCompilationUnit(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitCompilationUnit(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitCompilationUnit(this);
			else return visitor.visitChildren(this);
		}
	}

	public final CompilationUnitContext compilationUnit() throws RecognitionException {
		CompilationUnitContext _localctx = new CompilationUnitContext(_ctx, getState());
		enterRule(_localctx, 0, RULE_compilationUnit);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(69);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 16805906L) != 0)) {
				{
				{
				setState(66);
				topLevelElement();
				}
				}
				setState(71);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			setState(72);
			match(EOF);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class TopLevelElementContext extends ParserRuleContext {
		public ModeltypeDeclContext modeltypeDecl() {
			return getRuleContext(ModeltypeDeclContext.class,0);
		}
		public TransformationDeclContext transformationDecl() {
			return getRuleContext(TransformationDeclContext.class,0);
		}
		public MainDeclContext mainDecl() {
			return getRuleContext(MainDeclContext.class,0);
		}
		public MappingDeclContext mappingDecl() {
			return getRuleContext(MappingDeclContext.class,0);
		}
		public ConstructorDeclContext constructorDecl() {
			return getRuleContext(ConstructorDeclContext.class,0);
		}
		public TopLevelElementContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_topLevelElement; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterTopLevelElement(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitTopLevelElement(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitTopLevelElement(this);
			else return visitor.visitChildren(this);
		}
	}

	public final TopLevelElementContext topLevelElement() throws RecognitionException {
		TopLevelElementContext _localctx = new TopLevelElementContext(_ctx, getState());
		enterRule(_localctx, 2, RULE_topLevelElement);
		try {
			setState(79);
			_errHandler.sync(this);
			switch (_input.LA(1)) {
			case T__0:
				enterOuterAlt(_localctx, 1);
				{
				setState(74);
				modeltypeDecl();
				}
				break;
			case T__3:
				enterOuterAlt(_localctx, 2);
				{
				setState(75);
				transformationDecl();
				}
				break;
			case T__11:
				enterOuterAlt(_localctx, 3);
				{
				setState(76);
				mainDecl();
				}
				break;
			case T__12:
			case T__13:
				enterOuterAlt(_localctx, 4);
				{
				setState(77);
				mappingDecl();
				}
				break;
			case T__23:
				enterOuterAlt(_localctx, 5);
				{
				setState(78);
				constructorDecl();
				}
				break;
			default:
				throw new NoViableAltException(this);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ModeltypeDeclContext extends ParserRuleContext {
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public TerminalNode StringLiteral() { return getToken(QVTOParser.StringLiteral, 0); }
		public ModeltypeDeclContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_modeltypeDecl; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterModeltypeDecl(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitModeltypeDecl(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitModeltypeDecl(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ModeltypeDeclContext modeltypeDecl() throws RecognitionException {
		ModeltypeDeclContext _localctx = new ModeltypeDeclContext(_ctx, getState());
		enterRule(_localctx, 4, RULE_modeltypeDecl);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(81);
			match(T__0);
			setState(82);
			match(IDENTIFIER);
			setState(83);
			match(T__1);
			setState(84);
			match(StringLiteral);
			setState(85);
			match(T__2);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class TransformationDeclContext extends ParserRuleContext {
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public TransformParamListContext transformParamList() {
			return getRuleContext(TransformParamListContext.class,0);
		}
		public TransformationDeclContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_transformationDecl; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterTransformationDecl(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitTransformationDecl(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitTransformationDecl(this);
			else return visitor.visitChildren(this);
		}
	}

	public final TransformationDeclContext transformationDecl() throws RecognitionException {
		TransformationDeclContext _localctx = new TransformationDeclContext(_ctx, getState());
		enterRule(_localctx, 6, RULE_transformationDecl);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(87);
			match(T__3);
			setState(88);
			match(IDENTIFIER);
			setState(89);
			match(T__4);
			setState(90);
			transformParamList();
			setState(91);
			match(T__5);
			setState(92);
			match(T__2);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class TransformParamListContext extends ParserRuleContext {
		public List<TransformParamContext> transformParam() {
			return getRuleContexts(TransformParamContext.class);
		}
		public TransformParamContext transformParam(int i) {
			return getRuleContext(TransformParamContext.class,i);
		}
		public TransformParamListContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_transformParamList; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterTransformParamList(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitTransformParamList(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitTransformParamList(this);
			else return visitor.visitChildren(this);
		}
	}

	public final TransformParamListContext transformParamList() throws RecognitionException {
		TransformParamListContext _localctx = new TransformParamListContext(_ctx, getState());
		enterRule(_localctx, 8, RULE_transformParamList);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(94);
			transformParam();
			setState(99);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__6) {
				{
				{
				setState(95);
				match(T__6);
				setState(96);
				transformParam();
				}
				}
				setState(101);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class TransformParamContext extends ParserRuleContext {
		public DirectionContext direction() {
			return getRuleContext(DirectionContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public TransformParamContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_transformParam; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterTransformParam(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitTransformParam(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitTransformParam(this);
			else return visitor.visitChildren(this);
		}
	}

	public final TransformParamContext transformParam() throws RecognitionException {
		TransformParamContext _localctx = new TransformParamContext(_ctx, getState());
		enterRule(_localctx, 10, RULE_transformParam);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(102);
			direction();
			setState(103);
			match(IDENTIFIER);
			setState(104);
			match(T__7);
			setState(105);
			typeRef();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class DirectionContext extends ParserRuleContext {
		public DirectionContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_direction; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterDirection(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitDirection(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitDirection(this);
			else return visitor.visitChildren(this);
		}
	}

	public final DirectionContext direction() throws RecognitionException {
		DirectionContext _localctx = new DirectionContext(_ctx, getState());
		enterRule(_localctx, 12, RULE_direction);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(107);
			_la = _input.LA(1);
			if ( !((((_la) & ~0x3f) == 0 && ((1L << _la) & 3584L) != 0)) ) {
			_errHandler.recoverInline(this);
			}
			else {
				if ( _input.LA(1)==Token.EOF ) matchedEOF = true;
				_errHandler.reportMatch(this);
				consume();
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class MainDeclContext extends ParserRuleContext {
		public BlockContext block() {
			return getRuleContext(BlockContext.class,0);
		}
		public MainDeclContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_mainDecl; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterMainDecl(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitMainDecl(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitMainDecl(this);
			else return visitor.visitChildren(this);
		}
	}

	public final MainDeclContext mainDecl() throws RecognitionException {
		MainDeclContext _localctx = new MainDeclContext(_ctx, getState());
		enterRule(_localctx, 14, RULE_mainDecl);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(109);
			match(T__11);
			setState(110);
			match(T__4);
			setState(111);
			match(T__5);
			setState(112);
			block();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class MappingDeclContext extends ParserRuleContext {
		public QualifiedNameContext qualifiedName() {
			return getRuleContext(QualifiedNameContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public ReturnTypeContext returnType() {
			return getRuleContext(ReturnTypeContext.class,0);
		}
		public MappingBlockContext mappingBlock() {
			return getRuleContext(MappingBlockContext.class,0);
		}
		public FormalParamListContext formalParamList() {
			return getRuleContext(FormalParamListContext.class,0);
		}
		public List<MappingExtensionContext> mappingExtension() {
			return getRuleContexts(MappingExtensionContext.class);
		}
		public MappingExtensionContext mappingExtension(int i) {
			return getRuleContext(MappingExtensionContext.class,i);
		}
		public MappingDeclContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_mappingDecl; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterMappingDecl(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitMappingDecl(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitMappingDecl(this);
			else return visitor.visitChildren(this);
		}
	}

	public final MappingDeclContext mappingDecl() throws RecognitionException {
		MappingDeclContext _localctx = new MappingDeclContext(_ctx, getState());
		enterRule(_localctx, 16, RULE_mappingDecl);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(115);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==T__12) {
				{
				setState(114);
				match(T__12);
				}
			}

			setState(117);
			match(T__13);
			setState(118);
			qualifiedName();
			setState(119);
			match(T__14);
			setState(120);
			match(IDENTIFIER);
			setState(121);
			match(T__4);
			setState(123);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==IDENTIFIER) {
				{
				setState(122);
				formalParamList();
				}
			}

			setState(125);
			match(T__5);
			setState(126);
			match(T__7);
			setState(127);
			returnType();
			setState(131);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 1966080L) != 0)) {
				{
				{
				setState(128);
				mappingExtension();
				}
				}
				setState(133);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			setState(134);
			mappingBlock();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ReturnTypeContext extends ParserRuleContext {
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public ReturnTypeContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_returnType; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterReturnType(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitReturnType(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitReturnType(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ReturnTypeContext returnType() throws RecognitionException {
		ReturnTypeContext _localctx = new ReturnTypeContext(_ctx, getState());
		enterRule(_localctx, 18, RULE_returnType);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(136);
			typeRef();
			setState(139);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==T__15) {
				{
				setState(137);
				match(T__15);
				setState(138);
				match(IDENTIFIER);
				}
			}

			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class MappingExtensionContext extends ParserRuleContext {
		public List<MappingRefContext> mappingRef() {
			return getRuleContexts(MappingRefContext.class);
		}
		public MappingRefContext mappingRef(int i) {
			return getRuleContext(MappingRefContext.class,i);
		}
		public ExpressionContext expression() {
			return getRuleContext(ExpressionContext.class,0);
		}
		public MappingExtensionContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_mappingExtension; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterMappingExtension(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitMappingExtension(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitMappingExtension(this);
			else return visitor.visitChildren(this);
		}
	}

	public final MappingExtensionContext mappingExtension() throws RecognitionException {
		MappingExtensionContext _localctx = new MappingExtensionContext(_ctx, getState());
		enterRule(_localctx, 20, RULE_mappingExtension);
		int _la;
		try {
			setState(173);
			_errHandler.sync(this);
			switch (_input.LA(1)) {
			case T__16:
				enterOuterAlt(_localctx, 1);
				{
				setState(141);
				match(T__16);
				setState(142);
				mappingRef();
				setState(147);
				_errHandler.sync(this);
				_la = _input.LA(1);
				while (_la==T__6) {
					{
					{
					setState(143);
					match(T__6);
					setState(144);
					mappingRef();
					}
					}
					setState(149);
					_errHandler.sync(this);
					_la = _input.LA(1);
				}
				}
				break;
			case T__17:
				enterOuterAlt(_localctx, 2);
				{
				setState(150);
				match(T__17);
				setState(151);
				mappingRef();
				setState(156);
				_errHandler.sync(this);
				_la = _input.LA(1);
				while (_la==T__6) {
					{
					{
					setState(152);
					match(T__6);
					setState(153);
					mappingRef();
					}
					}
					setState(158);
					_errHandler.sync(this);
					_la = _input.LA(1);
				}
				}
				break;
			case T__18:
				enterOuterAlt(_localctx, 3);
				{
				setState(159);
				match(T__18);
				setState(160);
				mappingRef();
				setState(165);
				_errHandler.sync(this);
				_la = _input.LA(1);
				while (_la==T__6) {
					{
					{
					setState(161);
					match(T__6);
					setState(162);
					mappingRef();
					}
					}
					setState(167);
					_errHandler.sync(this);
					_la = _input.LA(1);
				}
				}
				break;
			case T__19:
				enterOuterAlt(_localctx, 4);
				{
				setState(168);
				match(T__19);
				setState(169);
				match(T__20);
				setState(170);
				expression();
				setState(171);
				match(T__21);
				}
				break;
			default:
				throw new NoViableAltException(this);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class MappingRefContext extends ParserRuleContext {
		public QualifiedNameContext qualifiedName() {
			return getRuleContext(QualifiedNameContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public MappingRefContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_mappingRef; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterMappingRef(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitMappingRef(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitMappingRef(this);
			else return visitor.visitChildren(this);
		}
	}

	public final MappingRefContext mappingRef() throws RecognitionException {
		MappingRefContext _localctx = new MappingRefContext(_ctx, getState());
		enterRule(_localctx, 22, RULE_mappingRef);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(175);
			qualifiedName();
			setState(176);
			match(T__14);
			setState(177);
			match(IDENTIFIER);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class MappingBlockContext extends ParserRuleContext {
		public InitSectionContext initSection() {
			return getRuleContext(InitSectionContext.class,0);
		}
		public List<StatementContext> statement() {
			return getRuleContexts(StatementContext.class);
		}
		public StatementContext statement(int i) {
			return getRuleContext(StatementContext.class,i);
		}
		public MappingBlockContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_mappingBlock; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterMappingBlock(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitMappingBlock(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitMappingBlock(this);
			else return visitor.visitChildren(this);
		}
	}

	public final MappingBlockContext mappingBlock() throws RecognitionException {
		MappingBlockContext _localctx = new MappingBlockContext(_ctx, getState());
		enterRule(_localctx, 24, RULE_mappingBlock);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(179);
			match(T__20);
			setState(181);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==T__22) {
				{
				setState(180);
				initSection();
				}
			}

			setState(186);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279561175072L) != 0)) {
				{
				{
				setState(183);
				statement();
				}
				}
				setState(188);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			setState(189);
			match(T__21);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class InitSectionContext extends ParserRuleContext {
		public BlockContext block() {
			return getRuleContext(BlockContext.class,0);
		}
		public InitSectionContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_initSection; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterInitSection(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitInitSection(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitInitSection(this);
			else return visitor.visitChildren(this);
		}
	}

	public final InitSectionContext initSection() throws RecognitionException {
		InitSectionContext _localctx = new InitSectionContext(_ctx, getState());
		enterRule(_localctx, 26, RULE_initSection);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(191);
			match(T__22);
			setState(192);
			block();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ConstructorDeclContext extends ParserRuleContext {
		public QualifiedNameContext qualifiedName() {
			return getRuleContext(QualifiedNameContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public BlockContext block() {
			return getRuleContext(BlockContext.class,0);
		}
		public FormalParamListContext formalParamList() {
			return getRuleContext(FormalParamListContext.class,0);
		}
		public ConstructorDeclContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_constructorDecl; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterConstructorDecl(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitConstructorDecl(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitConstructorDecl(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ConstructorDeclContext constructorDecl() throws RecognitionException {
		ConstructorDeclContext _localctx = new ConstructorDeclContext(_ctx, getState());
		enterRule(_localctx, 28, RULE_constructorDecl);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(194);
			match(T__23);
			setState(195);
			qualifiedName();
			setState(196);
			match(T__14);
			setState(197);
			match(IDENTIFIER);
			setState(198);
			match(T__4);
			setState(200);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==IDENTIFIER) {
				{
				setState(199);
				formalParamList();
				}
			}

			setState(202);
			match(T__5);
			setState(203);
			block();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class FormalParamListContext extends ParserRuleContext {
		public List<FormalParamContext> formalParam() {
			return getRuleContexts(FormalParamContext.class);
		}
		public FormalParamContext formalParam(int i) {
			return getRuleContext(FormalParamContext.class,i);
		}
		public FormalParamListContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_formalParamList; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterFormalParamList(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitFormalParamList(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitFormalParamList(this);
			else return visitor.visitChildren(this);
		}
	}

	public final FormalParamListContext formalParamList() throws RecognitionException {
		FormalParamListContext _localctx = new FormalParamListContext(_ctx, getState());
		enterRule(_localctx, 30, RULE_formalParamList);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(205);
			formalParam();
			setState(210);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__6) {
				{
				{
				setState(206);
				match(T__6);
				setState(207);
				formalParam();
				}
				}
				setState(212);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class FormalParamContext extends ParserRuleContext {
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public FormalParamContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_formalParam; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterFormalParam(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitFormalParam(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitFormalParam(this);
			else return visitor.visitChildren(this);
		}
	}

	public final FormalParamContext formalParam() throws RecognitionException {
		FormalParamContext _localctx = new FormalParamContext(_ctx, getState());
		enterRule(_localctx, 32, RULE_formalParam);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(213);
			match(IDENTIFIER);
			setState(214);
			match(T__7);
			setState(215);
			typeRef();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class TypeRefContext extends ParserRuleContext {
		public QualifiedNameContext qualifiedName() {
			return getRuleContext(QualifiedNameContext.class,0);
		}
		public TypeRefContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_typeRef; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterTypeRef(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitTypeRef(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitTypeRef(this);
			else return visitor.visitChildren(this);
		}
	}

	public final TypeRefContext typeRef() throws RecognitionException {
		TypeRefContext _localctx = new TypeRefContext(_ctx, getState());
		enterRule(_localctx, 34, RULE_typeRef);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(217);
			qualifiedName();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class QualifiedNameContext extends ParserRuleContext {
		public List<TerminalNode> IDENTIFIER() { return getTokens(QVTOParser.IDENTIFIER); }
		public TerminalNode IDENTIFIER(int i) {
			return getToken(QVTOParser.IDENTIFIER, i);
		}
		public QualifiedNameContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_qualifiedName; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterQualifiedName(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitQualifiedName(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitQualifiedName(this);
			else return visitor.visitChildren(this);
		}
	}

	public final QualifiedNameContext qualifiedName() throws RecognitionException {
		QualifiedNameContext _localctx = new QualifiedNameContext(_ctx, getState());
		enterRule(_localctx, 36, RULE_qualifiedName);
		try {
			int _alt;
			enterOuterAlt(_localctx, 1);
			{
			setState(219);
			match(IDENTIFIER);
			setState(224);
			_errHandler.sync(this);
			_alt = getInterpreter().adaptivePredict(_input,15,_ctx);
			while ( _alt!=2 && _alt!=org.antlr.v4.runtime.atn.ATN.INVALID_ALT_NUMBER ) {
				if ( _alt==1 ) {
					{
					{
					setState(220);
					match(T__14);
					setState(221);
					match(IDENTIFIER);
					}
					} 
				}
				setState(226);
				_errHandler.sync(this);
				_alt = getInterpreter().adaptivePredict(_input,15,_ctx);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class BlockContext extends ParserRuleContext {
		public List<StatementContext> statement() {
			return getRuleContexts(StatementContext.class);
		}
		public StatementContext statement(int i) {
			return getRuleContext(StatementContext.class,i);
		}
		public BlockContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_block; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterBlock(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitBlock(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitBlock(this);
			else return visitor.visitChildren(this);
		}
	}

	public final BlockContext block() throws RecognitionException {
		BlockContext _localctx = new BlockContext(_ctx, getState());
		enterRule(_localctx, 38, RULE_block);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(227);
			match(T__20);
			setState(231);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279561175072L) != 0)) {
				{
				{
				setState(228);
				statement();
				}
				}
				setState(233);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			setState(234);
			match(T__21);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class StatementContext extends ParserRuleContext {
		public StatementContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_statement; }
	 
		public StatementContext() { }
		public void copyFrom(StatementContext ctx) {
			super.copyFrom(ctx);
		}
	}
	@SuppressWarnings("CheckReturnValue")
	public static class IfStmtContext extends StatementContext {
		public ExpressionContext expression() {
			return getRuleContext(ExpressionContext.class,0);
		}
		public List<BlockContext> block() {
			return getRuleContexts(BlockContext.class);
		}
		public BlockContext block(int i) {
			return getRuleContext(BlockContext.class,i);
		}
		public IfStmtContext(StatementContext ctx) { copyFrom(ctx); }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterIfStmt(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitIfStmt(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitIfStmt(this);
			else return visitor.visitChildren(this);
		}
	}
	@SuppressWarnings("CheckReturnValue")
	public static class ExprOrAssignStmtContext extends StatementContext {
		public List<ExpressionContext> expression() {
			return getRuleContexts(ExpressionContext.class);
		}
		public ExpressionContext expression(int i) {
			return getRuleContext(ExpressionContext.class,i);
		}
		public ExprOrAssignStmtContext(StatementContext ctx) { copyFrom(ctx); }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterExprOrAssignStmt(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitExprOrAssignStmt(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitExprOrAssignStmt(this);
			else return visitor.visitChildren(this);
		}
	}
	@SuppressWarnings("CheckReturnValue")
	public static class VarDeclStmtContext extends StatementContext {
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public ExpressionContext expression() {
			return getRuleContext(ExpressionContext.class,0);
		}
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public VarDeclStmtContext(StatementContext ctx) { copyFrom(ctx); }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterVarDeclStmt(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitVarDeclStmt(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitVarDeclStmt(this);
			else return visitor.visitChildren(this);
		}
	}

	public final StatementContext statement() throws RecognitionException {
		StatementContext _localctx = new StatementContext(_ctx, getState());
		enterRule(_localctx, 40, RULE_statement);
		int _la;
		try {
			setState(264);
			_errHandler.sync(this);
			switch (_input.LA(1)) {
			case T__24:
				_localctx = new VarDeclStmtContext(_localctx);
				enterOuterAlt(_localctx, 1);
				{
				setState(236);
				match(T__24);
				setState(237);
				match(IDENTIFIER);
				setState(240);
				_errHandler.sync(this);
				_la = _input.LA(1);
				if (_la==T__7) {
					{
					setState(238);
					match(T__7);
					setState(239);
					typeRef();
					}
				}

				setState(242);
				match(T__25);
				setState(243);
				expression();
				setState(244);
				match(T__2);
				}
				break;
			case T__4:
			case T__33:
			case T__42:
			case T__43:
			case T__44:
			case T__45:
			case T__46:
			case T__47:
			case T__48:
			case StringLiteral:
			case IntegerLiteral:
			case IDENTIFIER:
				_localctx = new ExprOrAssignStmtContext(_localctx);
				enterOuterAlt(_localctx, 2);
				{
				setState(246);
				expression();
				setState(249);
				_errHandler.sync(this);
				_la = _input.LA(1);
				if (_la==T__25 || _la==T__26) {
					{
					setState(247);
					_la = _input.LA(1);
					if ( !(_la==T__25 || _la==T__26) ) {
					_errHandler.recoverInline(this);
					}
					else {
						if ( _input.LA(1)==Token.EOF ) matchedEOF = true;
						_errHandler.reportMatch(this);
						consume();
					}
					setState(248);
					expression();
					}
				}

				setState(251);
				match(T__2);
				}
				break;
			case T__27:
				_localctx = new IfStmtContext(_localctx);
				enterOuterAlt(_localctx, 3);
				{
				setState(253);
				match(T__27);
				setState(254);
				expression();
				setState(255);
				match(T__28);
				setState(256);
				block();
				setState(259);
				_errHandler.sync(this);
				_la = _input.LA(1);
				if (_la==T__29) {
					{
					setState(257);
					match(T__29);
					setState(258);
					block();
					}
				}

				setState(261);
				match(T__30);
				setState(262);
				match(T__2);
				}
				break;
			default:
				throw new NoViableAltException(this);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ExpressionContext extends ParserRuleContext {
		public OrExprContext orExpr() {
			return getRuleContext(OrExprContext.class,0);
		}
		public ExpressionContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_expression; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterExpression(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitExpression(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitExpression(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ExpressionContext expression() throws RecognitionException {
		ExpressionContext _localctx = new ExpressionContext(_ctx, getState());
		enterRule(_localctx, 42, RULE_expression);
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(266);
			orExpr();
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class OrExprContext extends ParserRuleContext {
		public List<AndExprContext> andExpr() {
			return getRuleContexts(AndExprContext.class);
		}
		public AndExprContext andExpr(int i) {
			return getRuleContext(AndExprContext.class,i);
		}
		public OrExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_orExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterOrExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitOrExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitOrExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final OrExprContext orExpr() throws RecognitionException {
		OrExprContext _localctx = new OrExprContext(_ctx, getState());
		enterRule(_localctx, 44, RULE_orExpr);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(268);
			andExpr();
			setState(273);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__31) {
				{
				{
				setState(269);
				match(T__31);
				setState(270);
				andExpr();
				}
				}
				setState(275);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class AndExprContext extends ParserRuleContext {
		public List<NotExprContext> notExpr() {
			return getRuleContexts(NotExprContext.class);
		}
		public NotExprContext notExpr(int i) {
			return getRuleContext(NotExprContext.class,i);
		}
		public AndExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_andExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterAndExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitAndExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitAndExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final AndExprContext andExpr() throws RecognitionException {
		AndExprContext _localctx = new AndExprContext(_ctx, getState());
		enterRule(_localctx, 46, RULE_andExpr);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(276);
			notExpr();
			setState(281);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__32) {
				{
				{
				setState(277);
				match(T__32);
				setState(278);
				notExpr();
				}
				}
				setState(283);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class NotExprContext extends ParserRuleContext {
		public NotExprContext notExpr() {
			return getRuleContext(NotExprContext.class,0);
		}
		public ComparisonExprContext comparisonExpr() {
			return getRuleContext(ComparisonExprContext.class,0);
		}
		public NotExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_notExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterNotExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitNotExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitNotExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final NotExprContext notExpr() throws RecognitionException {
		NotExprContext _localctx = new NotExprContext(_ctx, getState());
		enterRule(_localctx, 48, RULE_notExpr);
		try {
			setState(287);
			_errHandler.sync(this);
			switch (_input.LA(1)) {
			case T__33:
				enterOuterAlt(_localctx, 1);
				{
				setState(284);
				match(T__33);
				setState(285);
				notExpr();
				}
				break;
			case T__4:
			case T__42:
			case T__43:
			case T__44:
			case T__45:
			case T__46:
			case T__47:
			case T__48:
			case StringLiteral:
			case IntegerLiteral:
			case IDENTIFIER:
				enterOuterAlt(_localctx, 2);
				{
				setState(286);
				comparisonExpr();
				}
				break;
			default:
				throw new NoViableAltException(this);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ComparisonExprContext extends ParserRuleContext {
		public List<AdditiveExprContext> additiveExpr() {
			return getRuleContexts(AdditiveExprContext.class);
		}
		public AdditiveExprContext additiveExpr(int i) {
			return getRuleContext(AdditiveExprContext.class,i);
		}
		public ComparisonExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_comparisonExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterComparisonExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitComparisonExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitComparisonExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ComparisonExprContext comparisonExpr() throws RecognitionException {
		ComparisonExprContext _localctx = new ComparisonExprContext(_ctx, getState());
		enterRule(_localctx, 50, RULE_comparisonExpr);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(289);
			additiveExpr();
			setState(292);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if ((((_la) & ~0x3f) == 0 && ((1L << _la) & 2164663517184L) != 0)) {
				{
				setState(290);
				_la = _input.LA(1);
				if ( !((((_la) & ~0x3f) == 0 && ((1L << _la) & 2164663517184L) != 0)) ) {
				_errHandler.recoverInline(this);
				}
				else {
					if ( _input.LA(1)==Token.EOF ) matchedEOF = true;
					_errHandler.reportMatch(this);
					consume();
				}
				setState(291);
				additiveExpr();
				}
			}

			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class AdditiveExprContext extends ParserRuleContext {
		public List<CallExprContext> callExpr() {
			return getRuleContexts(CallExprContext.class);
		}
		public CallExprContext callExpr(int i) {
			return getRuleContext(CallExprContext.class,i);
		}
		public AdditiveExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_additiveExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterAdditiveExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitAdditiveExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitAdditiveExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final AdditiveExprContext additiveExpr() throws RecognitionException {
		AdditiveExprContext _localctx = new AdditiveExprContext(_ctx, getState());
		enterRule(_localctx, 52, RULE_additiveExpr);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(294);
			callExpr();
			setState(299);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__40 || _la==T__41) {
				{
				{
				setState(295);
				_la = _input.LA(1);
				if ( !(_la==T__40 || _la==T__41) ) {
				_errHandler.recoverInline(this);
				}
				else {
					if ( _input.LA(1)==Token.EOF ) matchedEOF = true;
					_errHandler.reportMatch(this);
					consume();
				}
				setState(296);
				callExpr();
				}
				}
				setState(301);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class CallExprContext extends ParserRuleContext {
		public PrimaryExprContext primaryExpr() {
			return getRuleContext(PrimaryExprContext.class,0);
		}
		public List<SuffixContext> suffix() {
			return getRuleContexts(SuffixContext.class);
		}
		public SuffixContext suffix(int i) {
			return getRuleContext(SuffixContext.class,i);
		}
		public CallExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_callExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterCallExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitCallExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitCallExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final CallExprContext callExpr() throws RecognitionException {
		CallExprContext _localctx = new CallExprContext(_ctx, getState());
		enterRule(_localctx, 54, RULE_callExpr);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(302);
			primaryExpr();
			setState(306);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 30399297484750848L) != 0)) {
				{
				{
				setState(303);
				suffix();
				}
				}
				setState(308);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class PrimaryExprContext extends ParserRuleContext {
		public QualifiedNameContext qualifiedName() {
			return getRuleContext(QualifiedNameContext.class,0);
		}
		public TerminalNode StringLiteral() { return getToken(QVTOParser.StringLiteral, 0); }
		public TerminalNode IntegerLiteral() { return getToken(QVTOParser.IntegerLiteral, 0); }
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public ArgumentListContext argumentList() {
			return getRuleContext(ArgumentListContext.class,0);
		}
		public ObjectBodyContext objectBody() {
			return getRuleContext(ObjectBodyContext.class,0);
		}
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public ExpressionContext expression() {
			return getRuleContext(ExpressionContext.class,0);
		}
		public PrimaryExprContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_primaryExpr; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterPrimaryExpr(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitPrimaryExpr(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitPrimaryExpr(this);
			else return visitor.visitChildren(this);
		}
	}

	public final PrimaryExprContext primaryExpr() throws RecognitionException {
		PrimaryExprContext _localctx = new PrimaryExprContext(_ctx, getState());
		enterRule(_localctx, 56, RULE_primaryExpr);
		int _la;
		try {
			setState(337);
			_errHandler.sync(this);
			switch (_input.LA(1)) {
			case T__42:
				enterOuterAlt(_localctx, 1);
				{
				setState(309);
				match(T__42);
				}
				break;
			case T__43:
				enterOuterAlt(_localctx, 2);
				{
				setState(310);
				match(T__43);
				}
				break;
			case T__44:
				enterOuterAlt(_localctx, 3);
				{
				setState(311);
				match(T__44);
				}
				break;
			case T__45:
				enterOuterAlt(_localctx, 4);
				{
				setState(312);
				match(T__45);
				}
				break;
			case T__46:
				enterOuterAlt(_localctx, 5);
				{
				setState(313);
				match(T__46);
				}
				break;
			case IDENTIFIER:
				enterOuterAlt(_localctx, 6);
				{
				setState(314);
				qualifiedName();
				}
				break;
			case StringLiteral:
				enterOuterAlt(_localctx, 7);
				{
				setState(315);
				match(StringLiteral);
				}
				break;
			case IntegerLiteral:
				enterOuterAlt(_localctx, 8);
				{
				setState(316);
				match(IntegerLiteral);
				}
				break;
			case T__47:
				enterOuterAlt(_localctx, 9);
				{
				setState(317);
				match(T__47);
				setState(318);
				typeRef();
				setState(319);
				match(T__4);
				setState(321);
				_errHandler.sync(this);
				_la = _input.LA(1);
				if ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279259185184L) != 0)) {
					{
					setState(320);
					argumentList();
					}
				}

				setState(323);
				match(T__5);
				}
				break;
			case T__48:
				enterOuterAlt(_localctx, 10);
				{
				setState(325);
				match(T__48);
				setState(326);
				typeRef();
				setState(329);
				_errHandler.sync(this);
				_la = _input.LA(1);
				if (_la==T__15) {
					{
					setState(327);
					match(T__15);
					setState(328);
					match(IDENTIFIER);
					}
				}

				setState(331);
				objectBody();
				}
				break;
			case T__4:
				enterOuterAlt(_localctx, 11);
				{
				setState(333);
				match(T__4);
				setState(334);
				expression();
				setState(335);
				match(T__5);
				}
				break;
			default:
				throw new NoViableAltException(this);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class SuffixContext extends ParserRuleContext {
		public TerminalNode IDENTIFIER() { return getToken(QVTOParser.IDENTIFIER, 0); }
		public ArgumentListContext argumentList() {
			return getRuleContext(ArgumentListContext.class,0);
		}
		public TypeRefContext typeRef() {
			return getRuleContext(TypeRefContext.class,0);
		}
		public SuffixContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_suffix; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterSuffix(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitSuffix(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitSuffix(this);
			else return visitor.visitChildren(this);
		}
	}

	public final SuffixContext suffix() throws RecognitionException {
		SuffixContext _localctx = new SuffixContext(_ctx, getState());
		enterRule(_localctx, 58, RULE_suffix);
		int _la;
		try {
			setState(376);
			_errHandler.sync(this);
			switch ( getInterpreter().adaptivePredict(_input,36,_ctx) ) {
			case 1:
				enterOuterAlt(_localctx, 1);
				{
				setState(339);
				match(T__49);
				setState(340);
				match(IDENTIFIER);
				setState(346);
				_errHandler.sync(this);
				switch ( getInterpreter().adaptivePredict(_input,31,_ctx) ) {
				case 1:
					{
					setState(341);
					match(T__4);
					setState(343);
					_errHandler.sync(this);
					_la = _input.LA(1);
					if ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279259185184L) != 0)) {
						{
						setState(342);
						argumentList();
						}
					}

					setState(345);
					match(T__5);
					}
					break;
				}
				}
				break;
			case 2:
				enterOuterAlt(_localctx, 2);
				{
				setState(348);
				match(T__50);
				setState(349);
				match(IDENTIFIER);
				setState(355);
				_errHandler.sync(this);
				switch ( getInterpreter().adaptivePredict(_input,33,_ctx) ) {
				case 1:
					{
					setState(350);
					match(T__4);
					setState(352);
					_errHandler.sync(this);
					_la = _input.LA(1);
					if ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279259185184L) != 0)) {
						{
						setState(351);
						argumentList();
						}
					}

					setState(354);
					match(T__5);
					}
					break;
				}
				}
				break;
			case 3:
				enterOuterAlt(_localctx, 3);
				{
				setState(357);
				match(T__50);
				setState(358);
				match(T__51);
				setState(359);
				match(IDENTIFIER);
				setState(365);
				_errHandler.sync(this);
				switch ( getInterpreter().adaptivePredict(_input,35,_ctx) ) {
				case 1:
					{
					setState(360);
					match(T__4);
					setState(362);
					_errHandler.sync(this);
					_la = _input.LA(1);
					if ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279259185184L) != 0)) {
						{
						setState(361);
						argumentList();
						}
					}

					setState(364);
					match(T__5);
					}
					break;
				}
				}
				break;
			case 4:
				enterOuterAlt(_localctx, 4);
				{
				setState(367);
				match(T__52);
				setState(368);
				match(T__53);
				setState(369);
				typeRef();
				setState(370);
				match(T__54);
				}
				break;
			case 5:
				enterOuterAlt(_localctx, 5);
				{
				setState(372);
				match(T__53);
				setState(373);
				typeRef();
				setState(374);
				match(T__54);
				}
				break;
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ObjectBodyContext extends ParserRuleContext {
		public List<ObjectMemberContext> objectMember() {
			return getRuleContexts(ObjectMemberContext.class);
		}
		public ObjectMemberContext objectMember(int i) {
			return getRuleContext(ObjectMemberContext.class,i);
		}
		public ObjectBodyContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_objectBody; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterObjectBody(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitObjectBody(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitObjectBody(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ObjectBodyContext objectBody() throws RecognitionException {
		ObjectBodyContext _localctx = new ObjectBodyContext(_ctx, getState());
		enterRule(_localctx, 60, RULE_objectBody);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(378);
			match(T__20);
			setState(382);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while ((((_la) & ~0x3f) == 0 && ((1L << _la) & 505520279259185184L) != 0)) {
				{
				{
				setState(379);
				objectMember();
				}
				}
				setState(384);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			setState(385);
			match(T__21);
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ObjectMemberContext extends ParserRuleContext {
		public List<ExpressionContext> expression() {
			return getRuleContexts(ExpressionContext.class);
		}
		public ExpressionContext expression(int i) {
			return getRuleContext(ExpressionContext.class,i);
		}
		public ObjectMemberContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_objectMember; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterObjectMember(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitObjectMember(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitObjectMember(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ObjectMemberContext objectMember() throws RecognitionException {
		ObjectMemberContext _localctx = new ObjectMemberContext(_ctx, getState());
		enterRule(_localctx, 62, RULE_objectMember);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(387);
			expression();
			setState(390);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==T__25 || _la==T__26) {
				{
				setState(388);
				_la = _input.LA(1);
				if ( !(_la==T__25 || _la==T__26) ) {
				_errHandler.recoverInline(this);
				}
				else {
					if ( _input.LA(1)==Token.EOF ) matchedEOF = true;
					_errHandler.reportMatch(this);
					consume();
				}
				setState(389);
				expression();
				}
			}

			setState(393);
			_errHandler.sync(this);
			_la = _input.LA(1);
			if (_la==T__2) {
				{
				setState(392);
				match(T__2);
				}
			}

			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	@SuppressWarnings("CheckReturnValue")
	public static class ArgumentListContext extends ParserRuleContext {
		public List<ExpressionContext> expression() {
			return getRuleContexts(ExpressionContext.class);
		}
		public ExpressionContext expression(int i) {
			return getRuleContext(ExpressionContext.class,i);
		}
		public ArgumentListContext(ParserRuleContext parent, int invokingState) {
			super(parent, invokingState);
		}
		@Override public int getRuleIndex() { return RULE_argumentList; }
		@Override
		public void enterRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).enterArgumentList(this);
		}
		@Override
		public void exitRule(ParseTreeListener listener) {
			if ( listener instanceof QVTOListener ) ((QVTOListener)listener).exitArgumentList(this);
		}
		@Override
		public <T> T accept(ParseTreeVisitor<? extends T> visitor) {
			if ( visitor instanceof QVTOVisitor ) return ((QVTOVisitor<? extends T>)visitor).visitArgumentList(this);
			else return visitor.visitChildren(this);
		}
	}

	public final ArgumentListContext argumentList() throws RecognitionException {
		ArgumentListContext _localctx = new ArgumentListContext(_ctx, getState());
		enterRule(_localctx, 64, RULE_argumentList);
		int _la;
		try {
			enterOuterAlt(_localctx, 1);
			{
			setState(395);
			expression();
			setState(400);
			_errHandler.sync(this);
			_la = _input.LA(1);
			while (_la==T__6) {
				{
				{
				setState(396);
				match(T__6);
				setState(397);
				expression();
				}
				}
				setState(402);
				_errHandler.sync(this);
				_la = _input.LA(1);
			}
			}
		}
		catch (RecognitionException re) {
			_localctx.exception = re;
			_errHandler.reportError(this, re);
			_errHandler.recover(this, re);
		}
		finally {
			exitRule();
		}
		return _localctx;
	}

	public static final String _serializedATN =
		"\u0004\u0001<\u0194\u0002\u0000\u0007\u0000\u0002\u0001\u0007\u0001\u0002"+
		"\u0002\u0007\u0002\u0002\u0003\u0007\u0003\u0002\u0004\u0007\u0004\u0002"+
		"\u0005\u0007\u0005\u0002\u0006\u0007\u0006\u0002\u0007\u0007\u0007\u0002"+
		"\b\u0007\b\u0002\t\u0007\t\u0002\n\u0007\n\u0002\u000b\u0007\u000b\u0002"+
		"\f\u0007\f\u0002\r\u0007\r\u0002\u000e\u0007\u000e\u0002\u000f\u0007\u000f"+
		"\u0002\u0010\u0007\u0010\u0002\u0011\u0007\u0011\u0002\u0012\u0007\u0012"+
		"\u0002\u0013\u0007\u0013\u0002\u0014\u0007\u0014\u0002\u0015\u0007\u0015"+
		"\u0002\u0016\u0007\u0016\u0002\u0017\u0007\u0017\u0002\u0018\u0007\u0018"+
		"\u0002\u0019\u0007\u0019\u0002\u001a\u0007\u001a\u0002\u001b\u0007\u001b"+
		"\u0002\u001c\u0007\u001c\u0002\u001d\u0007\u001d\u0002\u001e\u0007\u001e"+
		"\u0002\u001f\u0007\u001f\u0002 \u0007 \u0001\u0000\u0005\u0000D\b\u0000"+
		"\n\u0000\f\u0000G\t\u0000\u0001\u0000\u0001\u0000\u0001\u0001\u0001\u0001"+
		"\u0001\u0001\u0001\u0001\u0001\u0001\u0003\u0001P\b\u0001\u0001\u0002"+
		"\u0001\u0002\u0001\u0002\u0001\u0002\u0001\u0002\u0001\u0002\u0001\u0003"+
		"\u0001\u0003\u0001\u0003\u0001\u0003\u0001\u0003\u0001\u0003\u0001\u0003"+
		"\u0001\u0004\u0001\u0004\u0001\u0004\u0005\u0004b\b\u0004\n\u0004\f\u0004"+
		"e\t\u0004\u0001\u0005\u0001\u0005\u0001\u0005\u0001\u0005\u0001\u0005"+
		"\u0001\u0006\u0001\u0006\u0001\u0007\u0001\u0007\u0001\u0007\u0001\u0007"+
		"\u0001\u0007\u0001\b\u0003\bt\b\b\u0001\b\u0001\b\u0001\b\u0001\b\u0001"+
		"\b\u0001\b\u0003\b|\b\b\u0001\b\u0001\b\u0001\b\u0001\b\u0005\b\u0082"+
		"\b\b\n\b\f\b\u0085\t\b\u0001\b\u0001\b\u0001\t\u0001\t\u0001\t\u0003\t"+
		"\u008c\b\t\u0001\n\u0001\n\u0001\n\u0001\n\u0005\n\u0092\b\n\n\n\f\n\u0095"+
		"\t\n\u0001\n\u0001\n\u0001\n\u0001\n\u0005\n\u009b\b\n\n\n\f\n\u009e\t"+
		"\n\u0001\n\u0001\n\u0001\n\u0001\n\u0005\n\u00a4\b\n\n\n\f\n\u00a7\t\n"+
		"\u0001\n\u0001\n\u0001\n\u0001\n\u0001\n\u0003\n\u00ae\b\n\u0001\u000b"+
		"\u0001\u000b\u0001\u000b\u0001\u000b\u0001\f\u0001\f\u0003\f\u00b6\b\f"+
		"\u0001\f\u0005\f\u00b9\b\f\n\f\f\f\u00bc\t\f\u0001\f\u0001\f\u0001\r\u0001"+
		"\r\u0001\r\u0001\u000e\u0001\u000e\u0001\u000e\u0001\u000e\u0001\u000e"+
		"\u0001\u000e\u0003\u000e\u00c9\b\u000e\u0001\u000e\u0001\u000e\u0001\u000e"+
		"\u0001\u000f\u0001\u000f\u0001\u000f\u0005\u000f\u00d1\b\u000f\n\u000f"+
		"\f\u000f\u00d4\t\u000f\u0001\u0010\u0001\u0010\u0001\u0010\u0001\u0010"+
		"\u0001\u0011\u0001\u0011\u0001\u0012\u0001\u0012\u0001\u0012\u0005\u0012"+
		"\u00df\b\u0012\n\u0012\f\u0012\u00e2\t\u0012\u0001\u0013\u0001\u0013\u0005"+
		"\u0013\u00e6\b\u0013\n\u0013\f\u0013\u00e9\t\u0013\u0001\u0013\u0001\u0013"+
		"\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0003\u0014\u00f1\b\u0014"+
		"\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014"+
		"\u0001\u0014\u0003\u0014\u00fa\b\u0014\u0001\u0014\u0001\u0014\u0001\u0014"+
		"\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0003\u0014"+
		"\u0104\b\u0014\u0001\u0014\u0001\u0014\u0001\u0014\u0003\u0014\u0109\b"+
		"\u0014\u0001\u0015\u0001\u0015\u0001\u0016\u0001\u0016\u0001\u0016\u0005"+
		"\u0016\u0110\b\u0016\n\u0016\f\u0016\u0113\t\u0016\u0001\u0017\u0001\u0017"+
		"\u0001\u0017\u0005\u0017\u0118\b\u0017\n\u0017\f\u0017\u011b\t\u0017\u0001"+
		"\u0018\u0001\u0018\u0001\u0018\u0003\u0018\u0120\b\u0018\u0001\u0019\u0001"+
		"\u0019\u0001\u0019\u0003\u0019\u0125\b\u0019\u0001\u001a\u0001\u001a\u0001"+
		"\u001a\u0005\u001a\u012a\b\u001a\n\u001a\f\u001a\u012d\t\u001a\u0001\u001b"+
		"\u0001\u001b\u0005\u001b\u0131\b\u001b\n\u001b\f\u001b\u0134\t\u001b\u0001"+
		"\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001"+
		"\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0003"+
		"\u001c\u0142\b\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0001"+
		"\u001c\u0001\u001c\u0003\u001c\u014a\b\u001c\u0001\u001c\u0001\u001c\u0001"+
		"\u001c\u0001\u001c\u0001\u001c\u0001\u001c\u0003\u001c\u0152\b\u001c\u0001"+
		"\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0003\u001d\u0158\b\u001d\u0001"+
		"\u001d\u0003\u001d\u015b\b\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0001"+
		"\u001d\u0003\u001d\u0161\b\u001d\u0001\u001d\u0003\u001d\u0164\b\u001d"+
		"\u0001\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0003\u001d"+
		"\u016b\b\u001d\u0001\u001d\u0003\u001d\u016e\b\u001d\u0001\u001d\u0001"+
		"\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0001\u001d\u0001"+
		"\u001d\u0001\u001d\u0003\u001d\u0179\b\u001d\u0001\u001e\u0001\u001e\u0005"+
		"\u001e\u017d\b\u001e\n\u001e\f\u001e\u0180\t\u001e\u0001\u001e\u0001\u001e"+
		"\u0001\u001f\u0001\u001f\u0001\u001f\u0003\u001f\u0187\b\u001f\u0001\u001f"+
		"\u0003\u001f\u018a\b\u001f\u0001 \u0001 \u0001 \u0005 \u018f\b \n \f "+
		"\u0192\t \u0001 \u0000\u0000!\u0000\u0002\u0004\u0006\b\n\f\u000e\u0010"+
		"\u0012\u0014\u0016\u0018\u001a\u001c\u001e \"$&(*,.02468:<>@\u0000\u0004"+
		"\u0001\u0000\t\u000b\u0001\u0000\u001a\u001b\u0001\u0000#(\u0001\u0000"+
		")*\u01ad\u0000E\u0001\u0000\u0000\u0000\u0002O\u0001\u0000\u0000\u0000"+
		"\u0004Q\u0001\u0000\u0000\u0000\u0006W\u0001\u0000\u0000\u0000\b^\u0001"+
		"\u0000\u0000\u0000\nf\u0001\u0000\u0000\u0000\fk\u0001\u0000\u0000\u0000"+
		"\u000em\u0001\u0000\u0000\u0000\u0010s\u0001\u0000\u0000\u0000\u0012\u0088"+
		"\u0001\u0000\u0000\u0000\u0014\u00ad\u0001\u0000\u0000\u0000\u0016\u00af"+
		"\u0001\u0000\u0000\u0000\u0018\u00b3\u0001\u0000\u0000\u0000\u001a\u00bf"+
		"\u0001\u0000\u0000\u0000\u001c\u00c2\u0001\u0000\u0000\u0000\u001e\u00cd"+
		"\u0001\u0000\u0000\u0000 \u00d5\u0001\u0000\u0000\u0000\"\u00d9\u0001"+
		"\u0000\u0000\u0000$\u00db\u0001\u0000\u0000\u0000&\u00e3\u0001\u0000\u0000"+
		"\u0000(\u0108\u0001\u0000\u0000\u0000*\u010a\u0001\u0000\u0000\u0000,"+
		"\u010c\u0001\u0000\u0000\u0000.\u0114\u0001\u0000\u0000\u00000\u011f\u0001"+
		"\u0000\u0000\u00002\u0121\u0001\u0000\u0000\u00004\u0126\u0001\u0000\u0000"+
		"\u00006\u012e\u0001\u0000\u0000\u00008\u0151\u0001\u0000\u0000\u0000:"+
		"\u0178\u0001\u0000\u0000\u0000<\u017a\u0001\u0000\u0000\u0000>\u0183\u0001"+
		"\u0000\u0000\u0000@\u018b\u0001\u0000\u0000\u0000BD\u0003\u0002\u0001"+
		"\u0000CB\u0001\u0000\u0000\u0000DG\u0001\u0000\u0000\u0000EC\u0001\u0000"+
		"\u0000\u0000EF\u0001\u0000\u0000\u0000FH\u0001\u0000\u0000\u0000GE\u0001"+
		"\u0000\u0000\u0000HI\u0005\u0000\u0000\u0001I\u0001\u0001\u0000\u0000"+
		"\u0000JP\u0003\u0004\u0002\u0000KP\u0003\u0006\u0003\u0000LP\u0003\u000e"+
		"\u0007\u0000MP\u0003\u0010\b\u0000NP\u0003\u001c\u000e\u0000OJ\u0001\u0000"+
		"\u0000\u0000OK\u0001\u0000\u0000\u0000OL\u0001\u0000\u0000\u0000OM\u0001"+
		"\u0000\u0000\u0000ON\u0001\u0000\u0000\u0000P\u0003\u0001\u0000\u0000"+
		"\u0000QR\u0005\u0001\u0000\u0000RS\u0005:\u0000\u0000ST\u0005\u0002\u0000"+
		"\u0000TU\u00058\u0000\u0000UV\u0005\u0003\u0000\u0000V\u0005\u0001\u0000"+
		"\u0000\u0000WX\u0005\u0004\u0000\u0000XY\u0005:\u0000\u0000YZ\u0005\u0005"+
		"\u0000\u0000Z[\u0003\b\u0004\u0000[\\\u0005\u0006\u0000\u0000\\]\u0005"+
		"\u0003\u0000\u0000]\u0007\u0001\u0000\u0000\u0000^c\u0003\n\u0005\u0000"+
		"_`\u0005\u0007\u0000\u0000`b\u0003\n\u0005\u0000a_\u0001\u0000\u0000\u0000"+
		"be\u0001\u0000\u0000\u0000ca\u0001\u0000\u0000\u0000cd\u0001\u0000\u0000"+
		"\u0000d\t\u0001\u0000\u0000\u0000ec\u0001\u0000\u0000\u0000fg\u0003\f"+
		"\u0006\u0000gh\u0005:\u0000\u0000hi\u0005\b\u0000\u0000ij\u0003\"\u0011"+
		"\u0000j\u000b\u0001\u0000\u0000\u0000kl\u0007\u0000\u0000\u0000l\r\u0001"+
		"\u0000\u0000\u0000mn\u0005\f\u0000\u0000no\u0005\u0005\u0000\u0000op\u0005"+
		"\u0006\u0000\u0000pq\u0003&\u0013\u0000q\u000f\u0001\u0000\u0000\u0000"+
		"rt\u0005\r\u0000\u0000sr\u0001\u0000\u0000\u0000st\u0001\u0000\u0000\u0000"+
		"tu\u0001\u0000\u0000\u0000uv\u0005\u000e\u0000\u0000vw\u0003$\u0012\u0000"+
		"wx\u0005\u000f\u0000\u0000xy\u0005:\u0000\u0000y{\u0005\u0005\u0000\u0000"+
		"z|\u0003\u001e\u000f\u0000{z\u0001\u0000\u0000\u0000{|\u0001\u0000\u0000"+
		"\u0000|}\u0001\u0000\u0000\u0000}~\u0005\u0006\u0000\u0000~\u007f\u0005"+
		"\b\u0000\u0000\u007f\u0083\u0003\u0012\t\u0000\u0080\u0082\u0003\u0014"+
		"\n\u0000\u0081\u0080\u0001\u0000\u0000\u0000\u0082\u0085\u0001\u0000\u0000"+
		"\u0000\u0083\u0081\u0001\u0000\u0000\u0000\u0083\u0084\u0001\u0000\u0000"+
		"\u0000\u0084\u0086\u0001\u0000\u0000\u0000\u0085\u0083\u0001\u0000\u0000"+
		"\u0000\u0086\u0087\u0003\u0018\f\u0000\u0087\u0011\u0001\u0000\u0000\u0000"+
		"\u0088\u008b\u0003\"\u0011\u0000\u0089\u008a\u0005\u0010\u0000\u0000\u008a"+
		"\u008c\u0005:\u0000\u0000\u008b\u0089\u0001\u0000\u0000\u0000\u008b\u008c"+
		"\u0001\u0000\u0000\u0000\u008c\u0013\u0001\u0000\u0000\u0000\u008d\u008e"+
		"\u0005\u0011\u0000\u0000\u008e\u0093\u0003\u0016\u000b\u0000\u008f\u0090"+
		"\u0005\u0007\u0000\u0000\u0090\u0092\u0003\u0016\u000b\u0000\u0091\u008f"+
		"\u0001\u0000\u0000\u0000\u0092\u0095\u0001\u0000\u0000\u0000\u0093\u0091"+
		"\u0001\u0000\u0000\u0000\u0093\u0094\u0001\u0000\u0000\u0000\u0094\u00ae"+
		"\u0001\u0000\u0000\u0000\u0095\u0093\u0001\u0000\u0000\u0000\u0096\u0097"+
		"\u0005\u0012\u0000\u0000\u0097\u009c\u0003\u0016\u000b\u0000\u0098\u0099"+
		"\u0005\u0007\u0000\u0000\u0099\u009b\u0003\u0016\u000b\u0000\u009a\u0098"+
		"\u0001\u0000\u0000\u0000\u009b\u009e\u0001\u0000\u0000\u0000\u009c\u009a"+
		"\u0001\u0000\u0000\u0000\u009c\u009d\u0001\u0000\u0000\u0000\u009d\u00ae"+
		"\u0001\u0000\u0000\u0000\u009e\u009c\u0001\u0000\u0000\u0000\u009f\u00a0"+
		"\u0005\u0013\u0000\u0000\u00a0\u00a5\u0003\u0016\u000b\u0000\u00a1\u00a2"+
		"\u0005\u0007\u0000\u0000\u00a2\u00a4\u0003\u0016\u000b\u0000\u00a3\u00a1"+
		"\u0001\u0000\u0000\u0000\u00a4\u00a7\u0001\u0000\u0000\u0000\u00a5\u00a3"+
		"\u0001\u0000\u0000\u0000\u00a5\u00a6\u0001\u0000\u0000\u0000\u00a6\u00ae"+
		"\u0001\u0000\u0000\u0000\u00a7\u00a5\u0001\u0000\u0000\u0000\u00a8\u00a9"+
		"\u0005\u0014\u0000\u0000\u00a9\u00aa\u0005\u0015\u0000\u0000\u00aa\u00ab"+
		"\u0003*\u0015\u0000\u00ab\u00ac\u0005\u0016\u0000\u0000\u00ac\u00ae\u0001"+
		"\u0000\u0000\u0000\u00ad\u008d\u0001\u0000\u0000\u0000\u00ad\u0096\u0001"+
		"\u0000\u0000\u0000\u00ad\u009f\u0001\u0000\u0000\u0000\u00ad\u00a8\u0001"+
		"\u0000\u0000\u0000\u00ae\u0015\u0001\u0000\u0000\u0000\u00af\u00b0\u0003"+
		"$\u0012\u0000\u00b0\u00b1\u0005\u000f\u0000\u0000\u00b1\u00b2\u0005:\u0000"+
		"\u0000\u00b2\u0017\u0001\u0000\u0000\u0000\u00b3\u00b5\u0005\u0015\u0000"+
		"\u0000\u00b4\u00b6\u0003\u001a\r\u0000\u00b5\u00b4\u0001\u0000\u0000\u0000"+
		"\u00b5\u00b6\u0001\u0000\u0000\u0000\u00b6\u00ba\u0001\u0000\u0000\u0000"+
		"\u00b7\u00b9\u0003(\u0014\u0000\u00b8\u00b7\u0001\u0000\u0000\u0000\u00b9"+
		"\u00bc\u0001\u0000\u0000\u0000\u00ba\u00b8\u0001\u0000\u0000\u0000\u00ba"+
		"\u00bb\u0001\u0000\u0000\u0000\u00bb\u00bd\u0001\u0000\u0000\u0000\u00bc"+
		"\u00ba\u0001\u0000\u0000\u0000\u00bd\u00be\u0005\u0016\u0000\u0000\u00be"+
		"\u0019\u0001\u0000\u0000\u0000\u00bf\u00c0\u0005\u0017\u0000\u0000\u00c0"+
		"\u00c1\u0003&\u0013\u0000\u00c1\u001b\u0001\u0000\u0000\u0000\u00c2\u00c3"+
		"\u0005\u0018\u0000\u0000\u00c3\u00c4\u0003$\u0012\u0000\u00c4\u00c5\u0005"+
		"\u000f\u0000\u0000\u00c5\u00c6\u0005:\u0000\u0000\u00c6\u00c8\u0005\u0005"+
		"\u0000\u0000\u00c7\u00c9\u0003\u001e\u000f\u0000\u00c8\u00c7\u0001\u0000"+
		"\u0000\u0000\u00c8\u00c9\u0001\u0000\u0000\u0000\u00c9\u00ca\u0001\u0000"+
		"\u0000\u0000\u00ca\u00cb\u0005\u0006\u0000\u0000\u00cb\u00cc\u0003&\u0013"+
		"\u0000\u00cc\u001d\u0001\u0000\u0000\u0000\u00cd\u00d2\u0003 \u0010\u0000"+
		"\u00ce\u00cf\u0005\u0007\u0000\u0000\u00cf\u00d1\u0003 \u0010\u0000\u00d0"+
		"\u00ce\u0001\u0000\u0000\u0000\u00d1\u00d4\u0001\u0000\u0000\u0000\u00d2"+
		"\u00d0\u0001\u0000\u0000\u0000\u00d2\u00d3\u0001\u0000\u0000\u0000\u00d3"+
		"\u001f\u0001\u0000\u0000\u0000\u00d4\u00d2\u0001\u0000\u0000\u0000\u00d5"+
		"\u00d6\u0005:\u0000\u0000\u00d6\u00d7\u0005\b\u0000\u0000\u00d7\u00d8"+
		"\u0003\"\u0011\u0000\u00d8!\u0001\u0000\u0000\u0000\u00d9\u00da\u0003"+
		"$\u0012\u0000\u00da#\u0001\u0000\u0000\u0000\u00db\u00e0\u0005:\u0000"+
		"\u0000\u00dc\u00dd\u0005\u000f\u0000\u0000\u00dd\u00df\u0005:\u0000\u0000"+
		"\u00de\u00dc\u0001\u0000\u0000\u0000\u00df\u00e2\u0001\u0000\u0000\u0000"+
		"\u00e0\u00de\u0001\u0000\u0000\u0000\u00e0\u00e1\u0001\u0000\u0000\u0000"+
		"\u00e1%\u0001\u0000\u0000\u0000\u00e2\u00e0\u0001\u0000\u0000\u0000\u00e3"+
		"\u00e7\u0005\u0015\u0000\u0000\u00e4\u00e6\u0003(\u0014\u0000\u00e5\u00e4"+
		"\u0001\u0000\u0000\u0000\u00e6\u00e9\u0001\u0000\u0000\u0000\u00e7\u00e5"+
		"\u0001\u0000\u0000\u0000\u00e7\u00e8\u0001\u0000\u0000\u0000\u00e8\u00ea"+
		"\u0001\u0000\u0000\u0000\u00e9\u00e7\u0001\u0000\u0000\u0000\u00ea\u00eb"+
		"\u0005\u0016\u0000\u0000\u00eb\'\u0001\u0000\u0000\u0000\u00ec\u00ed\u0005"+
		"\u0019\u0000\u0000\u00ed\u00f0\u0005:\u0000\u0000\u00ee\u00ef\u0005\b"+
		"\u0000\u0000\u00ef\u00f1\u0003\"\u0011\u0000\u00f0\u00ee\u0001\u0000\u0000"+
		"\u0000\u00f0\u00f1\u0001\u0000\u0000\u0000\u00f1\u00f2\u0001\u0000\u0000"+
		"\u0000\u00f2\u00f3\u0005\u001a\u0000\u0000\u00f3\u00f4\u0003*\u0015\u0000"+
		"\u00f4\u00f5\u0005\u0003\u0000\u0000\u00f5\u0109\u0001\u0000\u0000\u0000"+
		"\u00f6\u00f9\u0003*\u0015\u0000\u00f7\u00f8\u0007\u0001\u0000\u0000\u00f8"+
		"\u00fa\u0003*\u0015\u0000\u00f9\u00f7\u0001\u0000\u0000\u0000\u00f9\u00fa"+
		"\u0001\u0000\u0000\u0000\u00fa\u00fb\u0001\u0000\u0000\u0000\u00fb\u00fc"+
		"\u0005\u0003\u0000\u0000\u00fc\u0109\u0001\u0000\u0000\u0000\u00fd\u00fe"+
		"\u0005\u001c\u0000\u0000\u00fe\u00ff\u0003*\u0015\u0000\u00ff\u0100\u0005"+
		"\u001d\u0000\u0000\u0100\u0103\u0003&\u0013\u0000\u0101\u0102\u0005\u001e"+
		"\u0000\u0000\u0102\u0104\u0003&\u0013\u0000\u0103\u0101\u0001\u0000\u0000"+
		"\u0000\u0103\u0104\u0001\u0000\u0000\u0000\u0104\u0105\u0001\u0000\u0000"+
		"\u0000\u0105\u0106\u0005\u001f\u0000\u0000\u0106\u0107\u0005\u0003\u0000"+
		"\u0000\u0107\u0109\u0001\u0000\u0000\u0000\u0108\u00ec\u0001\u0000\u0000"+
		"\u0000\u0108\u00f6\u0001\u0000\u0000\u0000\u0108\u00fd\u0001\u0000\u0000"+
		"\u0000\u0109)\u0001\u0000\u0000\u0000\u010a\u010b\u0003,\u0016\u0000\u010b"+
		"+\u0001\u0000\u0000\u0000\u010c\u0111\u0003.\u0017\u0000\u010d\u010e\u0005"+
		" \u0000\u0000\u010e\u0110\u0003.\u0017\u0000\u010f\u010d\u0001\u0000\u0000"+
		"\u0000\u0110\u0113\u0001\u0000\u0000\u0000\u0111\u010f\u0001\u0000\u0000"+
		"\u0000\u0111\u0112\u0001\u0000\u0000\u0000\u0112-\u0001\u0000\u0000\u0000"+
		"\u0113\u0111\u0001\u0000\u0000\u0000\u0114\u0119\u00030\u0018\u0000\u0115"+
		"\u0116\u0005!\u0000\u0000\u0116\u0118\u00030\u0018\u0000\u0117\u0115\u0001"+
		"\u0000\u0000\u0000\u0118\u011b\u0001\u0000\u0000\u0000\u0119\u0117\u0001"+
		"\u0000\u0000\u0000\u0119\u011a\u0001\u0000\u0000\u0000\u011a/\u0001\u0000"+
		"\u0000\u0000\u011b\u0119\u0001\u0000\u0000\u0000\u011c\u011d\u0005\"\u0000"+
		"\u0000\u011d\u0120\u00030\u0018\u0000\u011e\u0120\u00032\u0019\u0000\u011f"+
		"\u011c\u0001\u0000\u0000\u0000\u011f\u011e\u0001\u0000\u0000\u0000\u0120"+
		"1\u0001\u0000\u0000\u0000\u0121\u0124\u00034\u001a\u0000\u0122\u0123\u0007"+
		"\u0002\u0000\u0000\u0123\u0125\u00034\u001a\u0000\u0124\u0122\u0001\u0000"+
		"\u0000\u0000\u0124\u0125\u0001\u0000\u0000\u0000\u01253\u0001\u0000\u0000"+
		"\u0000\u0126\u012b\u00036\u001b\u0000\u0127\u0128\u0007\u0003\u0000\u0000"+
		"\u0128\u012a\u00036\u001b\u0000\u0129\u0127\u0001\u0000\u0000\u0000\u012a"+
		"\u012d\u0001\u0000\u0000\u0000\u012b\u0129\u0001\u0000\u0000\u0000\u012b"+
		"\u012c\u0001\u0000\u0000\u0000\u012c5\u0001\u0000\u0000\u0000\u012d\u012b"+
		"\u0001\u0000\u0000\u0000\u012e\u0132\u00038\u001c\u0000\u012f\u0131\u0003"+
		":\u001d\u0000\u0130\u012f\u0001\u0000\u0000\u0000\u0131\u0134\u0001\u0000"+
		"\u0000\u0000\u0132\u0130\u0001\u0000\u0000\u0000\u0132\u0133\u0001\u0000"+
		"\u0000\u0000\u01337\u0001\u0000\u0000\u0000\u0134\u0132\u0001\u0000\u0000"+
		"\u0000\u0135\u0152\u0005+\u0000\u0000\u0136\u0152\u0005,\u0000\u0000\u0137"+
		"\u0152\u0005-\u0000\u0000\u0138\u0152\u0005.\u0000\u0000\u0139\u0152\u0005"+
		"/\u0000\u0000\u013a\u0152\u0003$\u0012\u0000\u013b\u0152\u00058\u0000"+
		"\u0000\u013c\u0152\u00059\u0000\u0000\u013d\u013e\u00050\u0000\u0000\u013e"+
		"\u013f\u0003\"\u0011\u0000\u013f\u0141\u0005\u0005\u0000\u0000\u0140\u0142"+
		"\u0003@ \u0000\u0141\u0140\u0001\u0000\u0000\u0000\u0141\u0142\u0001\u0000"+
		"\u0000\u0000\u0142\u0143\u0001\u0000\u0000\u0000\u0143\u0144\u0005\u0006"+
		"\u0000\u0000\u0144\u0152\u0001\u0000\u0000\u0000\u0145\u0146\u00051\u0000"+
		"\u0000\u0146\u0149\u0003\"\u0011\u0000\u0147\u0148\u0005\u0010\u0000\u0000"+
		"\u0148\u014a\u0005:\u0000\u0000\u0149\u0147\u0001\u0000\u0000\u0000\u0149"+
		"\u014a\u0001\u0000\u0000\u0000\u014a\u014b\u0001\u0000\u0000\u0000\u014b"+
		"\u014c\u0003<\u001e\u0000\u014c\u0152\u0001\u0000\u0000\u0000\u014d\u014e"+
		"\u0005\u0005\u0000\u0000\u014e\u014f\u0003*\u0015\u0000\u014f\u0150\u0005"+
		"\u0006\u0000\u0000\u0150\u0152\u0001\u0000\u0000\u0000\u0151\u0135\u0001"+
		"\u0000\u0000\u0000\u0151\u0136\u0001\u0000\u0000\u0000\u0151\u0137\u0001"+
		"\u0000\u0000\u0000\u0151\u0138\u0001\u0000\u0000\u0000\u0151\u0139\u0001"+
		"\u0000\u0000\u0000\u0151\u013a\u0001\u0000\u0000\u0000\u0151\u013b\u0001"+
		"\u0000\u0000\u0000\u0151\u013c\u0001\u0000\u0000\u0000\u0151\u013d\u0001"+
		"\u0000\u0000\u0000\u0151\u0145\u0001\u0000\u0000\u0000\u0151\u014d\u0001"+
		"\u0000\u0000\u0000\u01529\u0001\u0000\u0000\u0000\u0153\u0154\u00052\u0000"+
		"\u0000\u0154\u015a\u0005:\u0000\u0000\u0155\u0157\u0005\u0005\u0000\u0000"+
		"\u0156\u0158\u0003@ \u0000\u0157\u0156\u0001\u0000\u0000\u0000\u0157\u0158"+
		"\u0001\u0000\u0000\u0000\u0158\u0159\u0001\u0000\u0000\u0000\u0159\u015b"+
		"\u0005\u0006\u0000\u0000\u015a\u0155\u0001\u0000\u0000\u0000\u015a\u015b"+
		"\u0001\u0000\u0000\u0000\u015b\u0179\u0001\u0000\u0000\u0000\u015c\u015d"+
		"\u00053\u0000\u0000\u015d\u0163\u0005:\u0000\u0000\u015e\u0160\u0005\u0005"+
		"\u0000\u0000\u015f\u0161\u0003@ \u0000\u0160\u015f\u0001\u0000\u0000\u0000"+
		"\u0160\u0161\u0001\u0000\u0000\u0000\u0161\u0162\u0001\u0000\u0000\u0000"+
		"\u0162\u0164\u0005\u0006\u0000\u0000\u0163\u015e\u0001\u0000\u0000\u0000"+
		"\u0163\u0164\u0001\u0000\u0000\u0000\u0164\u0179\u0001\u0000\u0000\u0000"+
		"\u0165\u0166\u00053\u0000\u0000\u0166\u0167\u00054\u0000\u0000\u0167\u016d"+
		"\u0005:\u0000\u0000\u0168\u016a\u0005\u0005\u0000\u0000\u0169\u016b\u0003"+
		"@ \u0000\u016a\u0169\u0001\u0000\u0000\u0000\u016a\u016b\u0001\u0000\u0000"+
		"\u0000\u016b\u016c\u0001\u0000\u0000\u0000\u016c\u016e\u0005\u0006\u0000"+
		"\u0000\u016d\u0168\u0001\u0000\u0000\u0000\u016d\u016e\u0001\u0000\u0000"+
		"\u0000\u016e\u0179\u0001\u0000\u0000\u0000\u016f\u0170\u00055\u0000\u0000"+
		"\u0170\u0171\u00056\u0000\u0000\u0171\u0172\u0003\"\u0011\u0000\u0172"+
		"\u0173\u00057\u0000\u0000\u0173\u0179\u0001\u0000\u0000\u0000\u0174\u0175"+
		"\u00056\u0000\u0000\u0175\u0176\u0003\"\u0011\u0000\u0176\u0177\u0005"+
		"7\u0000\u0000\u0177\u0179\u0001\u0000\u0000\u0000\u0178\u0153\u0001\u0000"+
		"\u0000\u0000\u0178\u015c\u0001\u0000\u0000\u0000\u0178\u0165\u0001\u0000"+
		"\u0000\u0000\u0178\u016f\u0001\u0000\u0000\u0000\u0178\u0174\u0001\u0000"+
		"\u0000\u0000\u0179;\u0001\u0000\u0000\u0000\u017a\u017e\u0005\u0015\u0000"+
		"\u0000\u017b\u017d\u0003>\u001f\u0000\u017c\u017b\u0001\u0000\u0000\u0000"+
		"\u017d\u0180\u0001\u0000\u0000\u0000\u017e\u017c\u0001\u0000\u0000\u0000"+
		"\u017e\u017f\u0001\u0000\u0000\u0000\u017f\u0181\u0001\u0000\u0000\u0000"+
		"\u0180\u017e\u0001\u0000\u0000\u0000\u0181\u0182\u0005\u0016\u0000\u0000"+
		"\u0182=\u0001\u0000\u0000\u0000\u0183\u0186\u0003*\u0015\u0000\u0184\u0185"+
		"\u0007\u0001\u0000\u0000\u0185\u0187\u0003*\u0015\u0000\u0186\u0184\u0001"+
		"\u0000\u0000\u0000\u0186\u0187\u0001\u0000\u0000\u0000\u0187\u0189\u0001"+
		"\u0000\u0000\u0000\u0188\u018a\u0005\u0003\u0000\u0000\u0189\u0188\u0001"+
		"\u0000\u0000\u0000\u0189\u018a\u0001\u0000\u0000\u0000\u018a?\u0001\u0000"+
		"\u0000\u0000\u018b\u0190\u0003*\u0015\u0000\u018c\u018d\u0005\u0007\u0000"+
		"\u0000\u018d\u018f\u0003*\u0015\u0000\u018e\u018c\u0001\u0000\u0000\u0000"+
		"\u018f\u0192\u0001\u0000\u0000\u0000\u0190\u018e\u0001\u0000\u0000\u0000"+
		"\u0190\u0191\u0001\u0000\u0000\u0000\u0191A\u0001\u0000\u0000\u0000\u0192"+
		"\u0190\u0001\u0000\u0000\u0000)EOcs{\u0083\u008b\u0093\u009c\u00a5\u00ad"+
		"\u00b5\u00ba\u00c8\u00d2\u00e0\u00e7\u00f0\u00f9\u0103\u0108\u0111\u0119"+
		"\u011f\u0124\u012b\u0132\u0141\u0149\u0151\u0157\u015a\u0160\u0163\u016a"+
		"\u016d\u0178\u017e\u0186\u0189\u0190";
	public static final ATN _ATN =
		new ATNDeserializer().deserialize(_serializedATN.toCharArray());
	static {
		_decisionToDFA = new DFA[_ATN.getNumberOfDecisions()];
		for (int i = 0; i < _ATN.getNumberOfDecisions(); i++) {
			_decisionToDFA[i] = new DFA(_ATN.getDecisionState(i), i);
		}
	}
}