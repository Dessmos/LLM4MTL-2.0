// Generated from org/qvto/parser/QVTO.g4 by ANTLR 4.13.1
package org.qvto.parser;
import org.antlr.v4.runtime.tree.ParseTreeVisitor;

/**
 * This interface defines a complete generic visitor for a parse tree produced
 * by {@link QVTOParser}.
 *
 * @param <T> The return type of the visit operation. Use {@link Void} for
 * operations with no return type.
 */
public interface QVTOVisitor<T> extends ParseTreeVisitor<T> {
	/**
	 * Visit a parse tree produced by {@link QVTOParser#compilationUnit}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitCompilationUnit(QVTOParser.CompilationUnitContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#topLevelElement}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitTopLevelElement(QVTOParser.TopLevelElementContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#modeltypeDecl}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitModeltypeDecl(QVTOParser.ModeltypeDeclContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#transformationDecl}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitTransformationDecl(QVTOParser.TransformationDeclContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#transformParamList}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitTransformParamList(QVTOParser.TransformParamListContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#transformParam}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitTransformParam(QVTOParser.TransformParamContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#direction}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitDirection(QVTOParser.DirectionContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#mainDecl}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitMainDecl(QVTOParser.MainDeclContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#mappingDecl}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitMappingDecl(QVTOParser.MappingDeclContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#returnType}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitReturnType(QVTOParser.ReturnTypeContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#mappingExtension}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitMappingExtension(QVTOParser.MappingExtensionContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#mappingRef}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitMappingRef(QVTOParser.MappingRefContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#mappingBlock}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitMappingBlock(QVTOParser.MappingBlockContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#initSection}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitInitSection(QVTOParser.InitSectionContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#constructorDecl}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitConstructorDecl(QVTOParser.ConstructorDeclContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#formalParamList}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitFormalParamList(QVTOParser.FormalParamListContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#formalParam}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitFormalParam(QVTOParser.FormalParamContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#typeRef}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitTypeRef(QVTOParser.TypeRefContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#qualifiedName}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitQualifiedName(QVTOParser.QualifiedNameContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#block}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitBlock(QVTOParser.BlockContext ctx);
	/**
	 * Visit a parse tree produced by the {@code varDeclStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitVarDeclStmt(QVTOParser.VarDeclStmtContext ctx);
	/**
	 * Visit a parse tree produced by the {@code exprOrAssignStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitExprOrAssignStmt(QVTOParser.ExprOrAssignStmtContext ctx);
	/**
	 * Visit a parse tree produced by the {@code ifStmt}
	 * labeled alternative in {@link QVTOParser#statement}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitIfStmt(QVTOParser.IfStmtContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#expression}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitExpression(QVTOParser.ExpressionContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#orExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitOrExpr(QVTOParser.OrExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#andExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitAndExpr(QVTOParser.AndExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#notExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitNotExpr(QVTOParser.NotExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#comparisonExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitComparisonExpr(QVTOParser.ComparisonExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#additiveExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitAdditiveExpr(QVTOParser.AdditiveExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#callExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitCallExpr(QVTOParser.CallExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#primaryExpr}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitPrimaryExpr(QVTOParser.PrimaryExprContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#suffix}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitSuffix(QVTOParser.SuffixContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#objectBody}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitObjectBody(QVTOParser.ObjectBodyContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#objectMember}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitObjectMember(QVTOParser.ObjectMemberContext ctx);
	/**
	 * Visit a parse tree produced by {@link QVTOParser#argumentList}.
	 * @param ctx the parse tree
	 * @return the visitor result
	 */
	T visitArgumentList(QVTOParser.ArgumentListContext ctx);
}