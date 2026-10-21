// Generated from org/qvto/parser/QVTO.g4 by ANTLR 4.13.1
package org.qvto.parser;
import org.antlr.v4.runtime.tree.ParseTreeListener;

/**
 * This interface defines a complete listener for a parse tree produced by
 * {@link QVTOParser}.
 */
public interface QVTOListener extends ParseTreeListener {
	/**
	 * Enter a parse tree produced by {@link QVTOParser#compilationUnit}.
	 * @param ctx the parse tree
	 */
	void enterCompilationUnit(QVTOParser.CompilationUnitContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#compilationUnit}.
	 * @param ctx the parse tree
	 */
	void exitCompilationUnit(QVTOParser.CompilationUnitContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#topLevelElement}.
	 * @param ctx the parse tree
	 */
	void enterTopLevelElement(QVTOParser.TopLevelElementContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#topLevelElement}.
	 * @param ctx the parse tree
	 */
	void exitTopLevelElement(QVTOParser.TopLevelElementContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#modeltypeDecl}.
	 * @param ctx the parse tree
	 */
	void enterModeltypeDecl(QVTOParser.ModeltypeDeclContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#modeltypeDecl}.
	 * @param ctx the parse tree
	 */
	void exitModeltypeDecl(QVTOParser.ModeltypeDeclContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#transformationDecl}.
	 * @param ctx the parse tree
	 */
	void enterTransformationDecl(QVTOParser.TransformationDeclContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#transformationDecl}.
	 * @param ctx the parse tree
	 */
	void exitTransformationDecl(QVTOParser.TransformationDeclContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#transformParamList}.
	 * @param ctx the parse tree
	 */
	void enterTransformParamList(QVTOParser.TransformParamListContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#transformParamList}.
	 * @param ctx the parse tree
	 */
	void exitTransformParamList(QVTOParser.TransformParamListContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#transformParam}.
	 * @param ctx the parse tree
	 */
	void enterTransformParam(QVTOParser.TransformParamContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#transformParam}.
	 * @param ctx the parse tree
	 */
	void exitTransformParam(QVTOParser.TransformParamContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#direction}.
	 * @param ctx the parse tree
	 */
	void enterDirection(QVTOParser.DirectionContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#direction}.
	 * @param ctx the parse tree
	 */
	void exitDirection(QVTOParser.DirectionContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#mainDecl}.
	 * @param ctx the parse tree
	 */
	void enterMainDecl(QVTOParser.MainDeclContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#mainDecl}.
	 * @param ctx the parse tree
	 */
	void exitMainDecl(QVTOParser.MainDeclContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#mappingDecl}.
	 * @param ctx the parse tree
	 */
	void enterMappingDecl(QVTOParser.MappingDeclContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#mappingDecl}.
	 * @param ctx the parse tree
	 */
	void exitMappingDecl(QVTOParser.MappingDeclContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#returnType}.
	 * @param ctx the parse tree
	 */
	void enterReturnType(QVTOParser.ReturnTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#returnType}.
	 * @param ctx the parse tree
	 */
	void exitReturnType(QVTOParser.ReturnTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#mappingExtension}.
	 * @param ctx the parse tree
	 */
	void enterMappingExtension(QVTOParser.MappingExtensionContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#mappingExtension}.
	 * @param ctx the parse tree
	 */
	void exitMappingExtension(QVTOParser.MappingExtensionContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#mappingRef}.
	 * @param ctx the parse tree
	 */
	void enterMappingRef(QVTOParser.MappingRefContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#mappingRef}.
	 * @param ctx the parse tree
	 */
	void exitMappingRef(QVTOParser.MappingRefContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#mappingBlock}.
	 * @param ctx the parse tree
	 */
	void enterMappingBlock(QVTOParser.MappingBlockContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#mappingBlock}.
	 * @param ctx the parse tree
	 */
	void exitMappingBlock(QVTOParser.MappingBlockContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#initSection}.
	 * @param ctx the parse tree
	 */
	void enterInitSection(QVTOParser.InitSectionContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#initSection}.
	 * @param ctx the parse tree
	 */
	void exitInitSection(QVTOParser.InitSectionContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#constructorDecl}.
	 * @param ctx the parse tree
	 */
	void enterConstructorDecl(QVTOParser.ConstructorDeclContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#constructorDecl}.
	 * @param ctx the parse tree
	 */
	void exitConstructorDecl(QVTOParser.ConstructorDeclContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#formalParamList}.
	 * @param ctx the parse tree
	 */
	void enterFormalParamList(QVTOParser.FormalParamListContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#formalParamList}.
	 * @param ctx the parse tree
	 */
	void exitFormalParamList(QVTOParser.FormalParamListContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#formalParam}.
	 * @param ctx the parse tree
	 */
	void enterFormalParam(QVTOParser.FormalParamContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#formalParam}.
	 * @param ctx the parse tree
	 */
	void exitFormalParam(QVTOParser.FormalParamContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#typeRef}.
	 * @param ctx the parse tree
	 */
	void enterTypeRef(QVTOParser.TypeRefContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#typeRef}.
	 * @param ctx the parse tree
	 */
	void exitTypeRef(QVTOParser.TypeRefContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#qualifiedName}.
	 * @param ctx the parse tree
	 */
	void enterQualifiedName(QVTOParser.QualifiedNameContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#qualifiedName}.
	 * @param ctx the parse tree
	 */
	void exitQualifiedName(QVTOParser.QualifiedNameContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#block}.
	 * @param ctx the parse tree
	 */
	void enterBlock(QVTOParser.BlockContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#block}.
	 * @param ctx the parse tree
	 */
	void exitBlock(QVTOParser.BlockContext ctx);
	/**
	 * Enter a parse tree produced by the {@code varDeclStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void enterVarDeclStmt(QVTOParser.VarDeclStmtContext ctx);
	/**
	 * Exit a parse tree produced by the {@code varDeclStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void exitVarDeclStmt(QVTOParser.VarDeclStmtContext ctx);
	/**
	 * Enter a parse tree produced by the {@code exprOrAssignStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void enterExprOrAssignStmt(QVTOParser.ExprOrAssignStmtContext ctx);
	/**
	 * Exit a parse tree produced by the {@code exprOrAssignStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void exitExprOrAssignStmt(QVTOParser.ExprOrAssignStmtContext ctx);
	/**
	 * Enter a parse tree produced by the {@code ifStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void enterIfStmt(QVTOParser.IfStmtContext ctx);
	/**
	 * Exit a parse tree produced by the {@code ifStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 */
	void exitIfStmt(QVTOParser.IfStmtContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#expression}.
	 * @param ctx the parse tree
	 */
	void enterExpression(QVTOParser.ExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#expression}.
	 * @param ctx the parse tree
	 */
	void exitExpression(QVTOParser.ExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#orExpr}.
	 * @param ctx the parse tree
	 */
	void enterOrExpr(QVTOParser.OrExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#orExpr}.
	 * @param ctx the parse tree
	 */
	void exitOrExpr(QVTOParser.OrExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#andExpr}.
	 * @param ctx the parse tree
	 */
	void enterAndExpr(QVTOParser.AndExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#andExpr}.
	 * @param ctx the parse tree
	 */
	void exitAndExpr(QVTOParser.AndExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#notExpr}.
	 * @param ctx the parse tree
	 */
	void enterNotExpr(QVTOParser.NotExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#notExpr}.
	 * @param ctx the parse tree
	 */
	void exitNotExpr(QVTOParser.NotExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#comparisonExpr}.
	 * @param ctx the parse tree
	 */
	void enterComparisonExpr(QVTOParser.ComparisonExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#comparisonExpr}.
	 * @param ctx the parse tree
	 */
	void exitComparisonExpr(QVTOParser.ComparisonExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#additiveExpr}.
	 * @param ctx the parse tree
	 */
	void enterAdditiveExpr(QVTOParser.AdditiveExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#additiveExpr}.
	 * @param ctx the parse tree
	 */
	void exitAdditiveExpr(QVTOParser.AdditiveExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#callExpr}.
	 * @param ctx the parse tree
	 */
	void enterCallExpr(QVTOParser.CallExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#callExpr}.
	 * @param ctx the parse tree
	 */
	void exitCallExpr(QVTOParser.CallExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#primaryExpr}.
	 * @param ctx the parse tree
	 */
	void enterPrimaryExpr(QVTOParser.PrimaryExprContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#primaryExpr}.
	 * @param ctx the parse tree
	 */
	void exitPrimaryExpr(QVTOParser.PrimaryExprContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#suffix}.
	 * @param ctx the parse tree
	 */
	void enterSuffix(QVTOParser.SuffixContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#suffix}.
	 * @param ctx the parse tree
	 */
	void exitSuffix(QVTOParser.SuffixContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#objectBody}.
	 * @param ctx the parse tree
	 */
	void enterObjectBody(QVTOParser.ObjectBodyContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#objectBody}.
	 * @param ctx the parse tree
	 */
	void exitObjectBody(QVTOParser.ObjectBodyContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#objectMember}.
	 * @param ctx the parse tree
	 */
	void enterObjectMember(QVTOParser.ObjectMemberContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#objectMember}.
	 * @param ctx the parse tree
	 */
	void exitObjectMember(QVTOParser.ObjectMemberContext ctx);
	/**
	 * Enter a parse tree produced by {@link QVTOParser#argumentList}.
	 * @param ctx the parse tree
	 */
	void enterArgumentList(QVTOParser.ArgumentListContext ctx);
	/**
	 * Exit a parse tree produced by {@link QVTOParser#argumentList}.
	 * @param ctx the parse tree
	 */
	void exitArgumentList(QVTOParser.ArgumentListContext ctx);
}