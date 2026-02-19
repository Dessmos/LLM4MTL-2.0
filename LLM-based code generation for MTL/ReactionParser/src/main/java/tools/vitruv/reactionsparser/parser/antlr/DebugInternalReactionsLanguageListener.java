package tools.vitruv.reactionsparser.parser.antlr;
// Generated from DebugInternalReactionsLanguage.g4 by ANTLR 4.13.2
import org.antlr.v4.runtime.tree.ParseTreeListener;

/**
 * This interface defines a complete listener for a parse tree produced by
 * {@link DebugInternalReactionsLanguageParser}.
 */
public interface DebugInternalReactionsLanguageListener extends ParseTreeListener {
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsFile}.
	 * @param ctx the parse tree
	 */
	void enterRuleReactionsFile(DebugInternalReactionsLanguageParser.RuleReactionsFileContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsFile}.
	 * @param ctx the parse tree
	 */
	void exitRuleReactionsFile(DebugInternalReactionsLanguageParser.RuleReactionsFileContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetamodelImport}.
	 * @param ctx the parse tree
	 */
	void enterRuleMetamodelImport(DebugInternalReactionsLanguageParser.RuleMetamodelImportContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetamodelImport}.
	 * @param ctx the parse tree
	 */
	void exitRuleMetamodelImport(DebugInternalReactionsLanguageParser.RuleMetamodelImportContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsSegment}.
	 * @param ctx the parse tree
	 */
	void enterRuleReactionsSegment(DebugInternalReactionsLanguageParser.RuleReactionsSegmentContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsSegment}.
	 * @param ctx the parse tree
	 */
	void exitRuleReactionsSegment(DebugInternalReactionsLanguageParser.RuleReactionsSegmentContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsImport}.
	 * @param ctx the parse tree
	 */
	void enterRuleReactionsImport(DebugInternalReactionsLanguageParser.RuleReactionsImportContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReactionsImport}.
	 * @param ctx the parse tree
	 */
	void exitRuleReactionsImport(DebugInternalReactionsLanguageParser.RuleReactionsImportContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReaction}.
	 * @param ctx the parse tree
	 */
	void enterRuleReaction(DebugInternalReactionsLanguageParser.RuleReactionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleReaction}.
	 * @param ctx the parse tree
	 */
	void exitRuleReaction(DebugInternalReactionsLanguageParser.RuleReactionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineCall}.
	 * @param ctx the parse tree
	 */
	void enterRuleRoutineCall(DebugInternalReactionsLanguageParser.RuleRoutineCallContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineCall}.
	 * @param ctx the parse tree
	 */
	void exitRuleRoutineCall(DebugInternalReactionsLanguageParser.RuleRoutineCallContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleTrigger}.
	 * @param ctx the parse tree
	 */
	void enterRuleTrigger(DebugInternalReactionsLanguageParser.RuleTriggerContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleTrigger}.
	 * @param ctx the parse tree
	 */
	void exitRuleTrigger(DebugInternalReactionsLanguageParser.RuleTriggerContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleConcreteModelChange}.
	 * @param ctx the parse tree
	 */
	void enterRuleConcreteModelChange(DebugInternalReactionsLanguageParser.RuleConcreteModelChangeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleConcreteModelChange}.
	 * @param ctx the parse tree
	 */
	void exitRuleConcreteModelChange(DebugInternalReactionsLanguageParser.RuleConcreteModelChangeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleModelElementChange}.
	 * @param ctx the parse tree
	 */
	void enterRuleModelElementChange(DebugInternalReactionsLanguageParser.RuleModelElementChangeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleModelElementChange}.
	 * @param ctx the parse tree
	 */
	void exitRuleModelElementChange(DebugInternalReactionsLanguageParser.RuleModelElementChangeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleModelAttributeChange}.
	 * @param ctx the parse tree
	 */
	void enterRuleModelAttributeChange(DebugInternalReactionsLanguageParser.RuleModelAttributeChangeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleModelAttributeChange}.
	 * @param ctx the parse tree
	 */
	void exitRuleModelAttributeChange(DebugInternalReactionsLanguageParser.RuleModelAttributeChangeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleArbitraryModelChange}.
	 * @param ctx the parse tree
	 */
	void enterRuleArbitraryModelChange(DebugInternalReactionsLanguageParser.RuleArbitraryModelChangeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleArbitraryModelChange}.
	 * @param ctx the parse tree
	 */
	void exitRuleArbitraryModelChange(DebugInternalReactionsLanguageParser.RuleArbitraryModelChangeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementExistenceChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementExistenceChangeType(DebugInternalReactionsLanguageParser.RuleElementExistenceChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementExistenceChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementExistenceChangeType(DebugInternalReactionsLanguageParser.RuleElementExistenceChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementUsageChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementUsageChangeType(DebugInternalReactionsLanguageParser.RuleElementUsageChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementUsageChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementUsageChangeType(DebugInternalReactionsLanguageParser.RuleElementUsageChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementCreationChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementCreationChangeType(DebugInternalReactionsLanguageParser.RuleElementCreationChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementCreationChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementCreationChangeType(DebugInternalReactionsLanguageParser.RuleElementCreationChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementDeletionChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementDeletionChangeType(DebugInternalReactionsLanguageParser.RuleElementDeletionChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementDeletionChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementDeletionChangeType(DebugInternalReactionsLanguageParser.RuleElementDeletionChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementReferenceChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementReferenceChangeType(DebugInternalReactionsLanguageParser.RuleElementReferenceChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementReferenceChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementReferenceChangeType(DebugInternalReactionsLanguageParser.RuleElementReferenceChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementInsertionChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementInsertionChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionInListChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementInsertionInListChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionInListChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionInListChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementInsertionInListChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionInListChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionAsRootChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementInsertionAsRootChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionAsRootChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementInsertionAsRootChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementInsertionAsRootChangeType(DebugInternalReactionsLanguageParser.RuleElementInsertionAsRootChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementRemovalChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementRemovalChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalAsRootChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementRemovalAsRootChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalAsRootChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalAsRootChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementRemovalAsRootChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalAsRootChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalFromListChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementRemovalFromListChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalFromListChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementRemovalFromListChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementRemovalFromListChangeType(DebugInternalReactionsLanguageParser.RuleElementRemovalFromListChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementReplacementChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementReplacementChangeType(DebugInternalReactionsLanguageParser.RuleElementReplacementChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementReplacementChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementReplacementChangeType(DebugInternalReactionsLanguageParser.RuleElementReplacementChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementChangeType}.
	 * @param ctx the parse tree
	 */
	void enterRuleElementChangeType(DebugInternalReactionsLanguageParser.RuleElementChangeTypeContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleElementChangeType}.
	 * @param ctx the parse tree
	 */
	void exitRuleElementChangeType(DebugInternalReactionsLanguageParser.RuleElementChangeTypeContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutine}.
	 * @param ctx the parse tree
	 */
	void enterRuleRoutine(DebugInternalReactionsLanguageParser.RuleRoutineContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutine}.
	 * @param ctx the parse tree
	 */
	void exitRuleRoutine(DebugInternalReactionsLanguageParser.RuleRoutineContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineOverrideImportPath}.
	 * @param ctx the parse tree
	 */
	void enterRuleRoutineOverrideImportPath(DebugInternalReactionsLanguageParser.RuleRoutineOverrideImportPathContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineOverrideImportPath}.
	 * @param ctx the parse tree
	 */
	void exitRuleRoutineOverrideImportPath(DebugInternalReactionsLanguageParser.RuleRoutineOverrideImportPathContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineInput}.
	 * @param ctx the parse tree
	 */
	void enterRuleRoutineInput(DebugInternalReactionsLanguageParser.RuleRoutineInputContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRoutineInput}.
	 * @param ctx the parse tree
	 */
	void exitRuleRoutineInput(DebugInternalReactionsLanguageParser.RuleRoutineInputContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchBlock}.
	 * @param ctx the parse tree
	 */
	void enterRuleMatchBlock(DebugInternalReactionsLanguageParser.RuleMatchBlockContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchBlock}.
	 * @param ctx the parse tree
	 */
	void exitRuleMatchBlock(DebugInternalReactionsLanguageParser.RuleMatchBlockContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchStatement}.
	 * @param ctx the parse tree
	 */
	void enterRuleMatchStatement(DebugInternalReactionsLanguageParser.RuleMatchStatementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchStatement}.
	 * @param ctx the parse tree
	 */
	void exitRuleMatchStatement(DebugInternalReactionsLanguageParser.RuleMatchStatementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveOrRequireAbscenceOfModelElement}.
	 * @param ctx the parse tree
	 */
	void enterRuleRetrieveOrRequireAbscenceOfModelElement(DebugInternalReactionsLanguageParser.RuleRetrieveOrRequireAbscenceOfModelElementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveOrRequireAbscenceOfModelElement}.
	 * @param ctx the parse tree
	 */
	void exitRuleRetrieveOrRequireAbscenceOfModelElement(DebugInternalReactionsLanguageParser.RuleRetrieveOrRequireAbscenceOfModelElementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRequireAbscenceOfModelElement}.
	 * @param ctx the parse tree
	 */
	void enterRuleRequireAbscenceOfModelElement(DebugInternalReactionsLanguageParser.RuleRequireAbscenceOfModelElementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRequireAbscenceOfModelElement}.
	 * @param ctx the parse tree
	 */
	void exitRuleRequireAbscenceOfModelElement(DebugInternalReactionsLanguageParser.RuleRequireAbscenceOfModelElementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveModelElement}.
	 * @param ctx the parse tree
	 */
	void enterRuleRetrieveModelElement(DebugInternalReactionsLanguageParser.RuleRetrieveModelElementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveModelElement}.
	 * @param ctx the parse tree
	 */
	void exitRuleRetrieveModelElement(DebugInternalReactionsLanguageParser.RuleRetrieveModelElementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveModelElementTypeStatement}.
	 * @param ctx the parse tree
	 */
	void enterRuleRetrieveModelElementTypeStatement(DebugInternalReactionsLanguageParser.RuleRetrieveModelElementTypeStatementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleRetrieveModelElementTypeStatement}.
	 * @param ctx the parse tree
	 */
	void exitRuleRetrieveModelElementTypeStatement(DebugInternalReactionsLanguageParser.RuleRetrieveModelElementTypeStatementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchCheckStatement}.
	 * @param ctx the parse tree
	 */
	void enterRuleMatchCheckStatement(DebugInternalReactionsLanguageParser.RuleMatchCheckStatementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMatchCheckStatement}.
	 * @param ctx the parse tree
	 */
	void exitRuleMatchCheckStatement(DebugInternalReactionsLanguageParser.RuleMatchCheckStatementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleCreateBlock}.
	 * @param ctx the parse tree
	 */
	void enterRuleCreateBlock(DebugInternalReactionsLanguageParser.RuleCreateBlockContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleCreateBlock}.
	 * @param ctx the parse tree
	 */
	void exitRuleCreateBlock(DebugInternalReactionsLanguageParser.RuleCreateBlockContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleCreateStatement}.
	 * @param ctx the parse tree
	 */
	void enterRuleCreateStatement(DebugInternalReactionsLanguageParser.RuleCreateStatementContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleCreateStatement}.
	 * @param ctx the parse tree
	 */
	void exitRuleCreateStatement(DebugInternalReactionsLanguageParser.RuleCreateStatementContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleUpdateBlock}.
	 * @param ctx the parse tree
	 */
	void enterRuleUpdateBlock(DebugInternalReactionsLanguageParser.RuleUpdateBlockContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleUpdateBlock}.
	 * @param ctx the parse tree
	 */
	void exitRuleUpdateBlock(DebugInternalReactionsLanguageParser.RuleUpdateBlockContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleMetaclassReference(DebugInternalReactionsLanguageParser.RuleMetaclassReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleMetaclassReference(DebugInternalReactionsLanguageParser.RuleMetaclassReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleUnnamedMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleUnnamedMetaclassReference(DebugInternalReactionsLanguageParser.RuleUnnamedMetaclassReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleUnnamedMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleUnnamedMetaclassReference(DebugInternalReactionsLanguageParser.RuleUnnamedMetaclassReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNamedMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleNamedMetaclassReference(DebugInternalReactionsLanguageParser.RuleNamedMetaclassReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNamedMetaclassReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleNamedMetaclassReference(DebugInternalReactionsLanguageParser.RuleNamedMetaclassReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNamedJavaElementReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleNamedJavaElementReference(DebugInternalReactionsLanguageParser.RuleNamedJavaElementReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNamedJavaElementReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleNamedJavaElementReference(DebugInternalReactionsLanguageParser.RuleNamedJavaElementReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassEAttributeReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleMetaclassEAttributeReference(DebugInternalReactionsLanguageParser.RuleMetaclassEAttributeReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassEAttributeReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleMetaclassEAttributeReference(DebugInternalReactionsLanguageParser.RuleMetaclassEAttributeReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassEReferenceReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleMetaclassEReferenceReference(DebugInternalReactionsLanguageParser.RuleMetaclassEReferenceReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleMetaclassEReferenceReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleMetaclassEReferenceReference(DebugInternalReactionsLanguageParser.RuleMetaclassEReferenceReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXExpression(DebugInternalReactionsLanguageParser.RuleXExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXExpression(DebugInternalReactionsLanguageParser.RuleXExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAssignment}.
	 * @param ctx the parse tree
	 */
	void enterRuleXAssignment(DebugInternalReactionsLanguageParser.RuleXAssignmentContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAssignment}.
	 * @param ctx the parse tree
	 */
	void exitRuleXAssignment(DebugInternalReactionsLanguageParser.RuleXAssignmentContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpSingleAssign}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpSingleAssign(DebugInternalReactionsLanguageParser.RuleOpSingleAssignContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpSingleAssign}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpSingleAssign(DebugInternalReactionsLanguageParser.RuleOpSingleAssignContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpMultiAssign}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpMultiAssign(DebugInternalReactionsLanguageParser.RuleOpMultiAssignContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpMultiAssign}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpMultiAssign(DebugInternalReactionsLanguageParser.RuleOpMultiAssignContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXOrExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXOrExpression(DebugInternalReactionsLanguageParser.RuleXOrExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXOrExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXOrExpression(DebugInternalReactionsLanguageParser.RuleXOrExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpOr}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpOr(DebugInternalReactionsLanguageParser.RuleOpOrContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpOr}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpOr(DebugInternalReactionsLanguageParser.RuleOpOrContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAndExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXAndExpression(DebugInternalReactionsLanguageParser.RuleXAndExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAndExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXAndExpression(DebugInternalReactionsLanguageParser.RuleXAndExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpAnd}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpAnd(DebugInternalReactionsLanguageParser.RuleOpAndContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpAnd}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpAnd(DebugInternalReactionsLanguageParser.RuleOpAndContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXEqualityExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXEqualityExpression(DebugInternalReactionsLanguageParser.RuleXEqualityExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXEqualityExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXEqualityExpression(DebugInternalReactionsLanguageParser.RuleXEqualityExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpEquality}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpEquality(DebugInternalReactionsLanguageParser.RuleOpEqualityContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpEquality}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpEquality(DebugInternalReactionsLanguageParser.RuleOpEqualityContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXRelationalExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXRelationalExpression(DebugInternalReactionsLanguageParser.RuleXRelationalExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXRelationalExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXRelationalExpression(DebugInternalReactionsLanguageParser.RuleXRelationalExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpCompare}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpCompare(DebugInternalReactionsLanguageParser.RuleOpCompareContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpCompare}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpCompare(DebugInternalReactionsLanguageParser.RuleOpCompareContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXOtherOperatorExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXOtherOperatorExpression(DebugInternalReactionsLanguageParser.RuleXOtherOperatorExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXOtherOperatorExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXOtherOperatorExpression(DebugInternalReactionsLanguageParser.RuleXOtherOperatorExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpOther}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpOther(DebugInternalReactionsLanguageParser.RuleOpOtherContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpOther}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpOther(DebugInternalReactionsLanguageParser.RuleOpOtherContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAdditiveExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXAdditiveExpression(DebugInternalReactionsLanguageParser.RuleXAdditiveExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXAdditiveExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXAdditiveExpression(DebugInternalReactionsLanguageParser.RuleXAdditiveExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpAdd}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpAdd(DebugInternalReactionsLanguageParser.RuleOpAddContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpAdd}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpAdd(DebugInternalReactionsLanguageParser.RuleOpAddContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXMultiplicativeExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXMultiplicativeExpression(DebugInternalReactionsLanguageParser.RuleXMultiplicativeExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXMultiplicativeExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXMultiplicativeExpression(DebugInternalReactionsLanguageParser.RuleXMultiplicativeExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpMulti}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpMulti(DebugInternalReactionsLanguageParser.RuleOpMultiContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpMulti}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpMulti(DebugInternalReactionsLanguageParser.RuleOpMultiContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXUnaryOperation}.
	 * @param ctx the parse tree
	 */
	void enterRuleXUnaryOperation(DebugInternalReactionsLanguageParser.RuleXUnaryOperationContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXUnaryOperation}.
	 * @param ctx the parse tree
	 */
	void exitRuleXUnaryOperation(DebugInternalReactionsLanguageParser.RuleXUnaryOperationContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpUnary}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpUnary(DebugInternalReactionsLanguageParser.RuleOpUnaryContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpUnary}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpUnary(DebugInternalReactionsLanguageParser.RuleOpUnaryContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCastedExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXCastedExpression(DebugInternalReactionsLanguageParser.RuleXCastedExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCastedExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXCastedExpression(DebugInternalReactionsLanguageParser.RuleXCastedExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXPostfixOperation}.
	 * @param ctx the parse tree
	 */
	void enterRuleXPostfixOperation(DebugInternalReactionsLanguageParser.RuleXPostfixOperationContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXPostfixOperation}.
	 * @param ctx the parse tree
	 */
	void exitRuleXPostfixOperation(DebugInternalReactionsLanguageParser.RuleXPostfixOperationContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpPostfix}.
	 * @param ctx the parse tree
	 */
	void enterRuleOpPostfix(DebugInternalReactionsLanguageParser.RuleOpPostfixContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleOpPostfix}.
	 * @param ctx the parse tree
	 */
	void exitRuleOpPostfix(DebugInternalReactionsLanguageParser.RuleOpPostfixContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXMemberFeatureCall}.
	 * @param ctx the parse tree
	 */
	void enterRuleXMemberFeatureCall(DebugInternalReactionsLanguageParser.RuleXMemberFeatureCallContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXMemberFeatureCall}.
	 * @param ctx the parse tree
	 */
	void exitRuleXMemberFeatureCall(DebugInternalReactionsLanguageParser.RuleXMemberFeatureCallContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXPrimaryExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXPrimaryExpression(DebugInternalReactionsLanguageParser.RuleXPrimaryExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXPrimaryExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXPrimaryExpression(DebugInternalReactionsLanguageParser.RuleXPrimaryExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXLiteral(DebugInternalReactionsLanguageParser.RuleXLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXLiteral(DebugInternalReactionsLanguageParser.RuleXLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCollectionLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXCollectionLiteral(DebugInternalReactionsLanguageParser.RuleXCollectionLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCollectionLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXCollectionLiteral(DebugInternalReactionsLanguageParser.RuleXCollectionLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSetLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXSetLiteral(DebugInternalReactionsLanguageParser.RuleXSetLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSetLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXSetLiteral(DebugInternalReactionsLanguageParser.RuleXSetLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXListLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXListLiteral(DebugInternalReactionsLanguageParser.RuleXListLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXListLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXListLiteral(DebugInternalReactionsLanguageParser.RuleXListLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXClosure}.
	 * @param ctx the parse tree
	 */
	void enterRuleXClosure(DebugInternalReactionsLanguageParser.RuleXClosureContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXClosure}.
	 * @param ctx the parse tree
	 */
	void exitRuleXClosure(DebugInternalReactionsLanguageParser.RuleXClosureContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpressionInClosure}.
	 * @param ctx the parse tree
	 */
	void enterRuleXExpressionInClosure(DebugInternalReactionsLanguageParser.RuleXExpressionInClosureContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpressionInClosure}.
	 * @param ctx the parse tree
	 */
	void exitRuleXExpressionInClosure(DebugInternalReactionsLanguageParser.RuleXExpressionInClosureContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXShortClosure}.
	 * @param ctx the parse tree
	 */
	void enterRuleXShortClosure(DebugInternalReactionsLanguageParser.RuleXShortClosureContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXShortClosure}.
	 * @param ctx the parse tree
	 */
	void exitRuleXShortClosure(DebugInternalReactionsLanguageParser.RuleXShortClosureContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXParenthesizedExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXParenthesizedExpression(DebugInternalReactionsLanguageParser.RuleXParenthesizedExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXParenthesizedExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXParenthesizedExpression(DebugInternalReactionsLanguageParser.RuleXParenthesizedExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXIfExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXIfExpression(DebugInternalReactionsLanguageParser.RuleXIfExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXIfExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXIfExpression(DebugInternalReactionsLanguageParser.RuleXIfExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSwitchExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXSwitchExpression(DebugInternalReactionsLanguageParser.RuleXSwitchExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSwitchExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXSwitchExpression(DebugInternalReactionsLanguageParser.RuleXSwitchExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCasePart}.
	 * @param ctx the parse tree
	 */
	void enterRuleXCasePart(DebugInternalReactionsLanguageParser.RuleXCasePartContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCasePart}.
	 * @param ctx the parse tree
	 */
	void exitRuleXCasePart(DebugInternalReactionsLanguageParser.RuleXCasePartContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXForLoopExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXForLoopExpression(DebugInternalReactionsLanguageParser.RuleXForLoopExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXForLoopExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXForLoopExpression(DebugInternalReactionsLanguageParser.RuleXForLoopExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBasicForLoopExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXBasicForLoopExpression(DebugInternalReactionsLanguageParser.RuleXBasicForLoopExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBasicForLoopExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXBasicForLoopExpression(DebugInternalReactionsLanguageParser.RuleXBasicForLoopExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXWhileExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXWhileExpression(DebugInternalReactionsLanguageParser.RuleXWhileExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXWhileExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXWhileExpression(DebugInternalReactionsLanguageParser.RuleXWhileExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXDoWhileExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXDoWhileExpression(DebugInternalReactionsLanguageParser.RuleXDoWhileExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXDoWhileExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXDoWhileExpression(DebugInternalReactionsLanguageParser.RuleXDoWhileExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBlockExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXBlockExpression(DebugInternalReactionsLanguageParser.RuleXBlockExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBlockExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXBlockExpression(DebugInternalReactionsLanguageParser.RuleXBlockExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpressionOrVarDeclaration}.
	 * @param ctx the parse tree
	 */
	void enterRuleXExpressionOrVarDeclaration(DebugInternalReactionsLanguageParser.RuleXExpressionOrVarDeclarationContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXExpressionOrVarDeclaration}.
	 * @param ctx the parse tree
	 */
	void exitRuleXExpressionOrVarDeclaration(DebugInternalReactionsLanguageParser.RuleXExpressionOrVarDeclarationContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXVariableDeclaration}.
	 * @param ctx the parse tree
	 */
	void enterRuleXVariableDeclaration(DebugInternalReactionsLanguageParser.RuleXVariableDeclarationContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXVariableDeclaration}.
	 * @param ctx the parse tree
	 */
	void exitRuleXVariableDeclaration(DebugInternalReactionsLanguageParser.RuleXVariableDeclarationContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmFormalParameter}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmFormalParameter(DebugInternalReactionsLanguageParser.RuleJvmFormalParameterContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmFormalParameter}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmFormalParameter(DebugInternalReactionsLanguageParser.RuleJvmFormalParameterContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleFullJvmFormalParameter}.
	 * @param ctx the parse tree
	 */
	void enterRuleFullJvmFormalParameter(DebugInternalReactionsLanguageParser.RuleFullJvmFormalParameterContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleFullJvmFormalParameter}.
	 * @param ctx the parse tree
	 */
	void exitRuleFullJvmFormalParameter(DebugInternalReactionsLanguageParser.RuleFullJvmFormalParameterContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXFeatureCall}.
	 * @param ctx the parse tree
	 */
	void enterRuleXFeatureCall(DebugInternalReactionsLanguageParser.RuleXFeatureCallContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXFeatureCall}.
	 * @param ctx the parse tree
	 */
	void exitRuleXFeatureCall(DebugInternalReactionsLanguageParser.RuleXFeatureCallContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleFeatureCallID}.
	 * @param ctx the parse tree
	 */
	void enterRuleFeatureCallID(DebugInternalReactionsLanguageParser.RuleFeatureCallIDContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleFeatureCallID}.
	 * @param ctx the parse tree
	 */
	void exitRuleFeatureCallID(DebugInternalReactionsLanguageParser.RuleFeatureCallIDContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleIdOrSuper}.
	 * @param ctx the parse tree
	 */
	void enterRuleIdOrSuper(DebugInternalReactionsLanguageParser.RuleIdOrSuperContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleIdOrSuper}.
	 * @param ctx the parse tree
	 */
	void exitRuleIdOrSuper(DebugInternalReactionsLanguageParser.RuleIdOrSuperContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXConstructorCall}.
	 * @param ctx the parse tree
	 */
	void enterRuleXConstructorCall(DebugInternalReactionsLanguageParser.RuleXConstructorCallContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXConstructorCall}.
	 * @param ctx the parse tree
	 */
	void exitRuleXConstructorCall(DebugInternalReactionsLanguageParser.RuleXConstructorCallContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBooleanLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXBooleanLiteral(DebugInternalReactionsLanguageParser.RuleXBooleanLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXBooleanLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXBooleanLiteral(DebugInternalReactionsLanguageParser.RuleXBooleanLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXNullLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXNullLiteral(DebugInternalReactionsLanguageParser.RuleXNullLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXNullLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXNullLiteral(DebugInternalReactionsLanguageParser.RuleXNullLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXNumberLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXNumberLiteral(DebugInternalReactionsLanguageParser.RuleXNumberLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXNumberLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXNumberLiteral(DebugInternalReactionsLanguageParser.RuleXNumberLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXStringLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXStringLiteral(DebugInternalReactionsLanguageParser.RuleXStringLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXStringLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXStringLiteral(DebugInternalReactionsLanguageParser.RuleXStringLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXTypeLiteral}.
	 * @param ctx the parse tree
	 */
	void enterRuleXTypeLiteral(DebugInternalReactionsLanguageParser.RuleXTypeLiteralContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXTypeLiteral}.
	 * @param ctx the parse tree
	 */
	void exitRuleXTypeLiteral(DebugInternalReactionsLanguageParser.RuleXTypeLiteralContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXThrowExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXThrowExpression(DebugInternalReactionsLanguageParser.RuleXThrowExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXThrowExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXThrowExpression(DebugInternalReactionsLanguageParser.RuleXThrowExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXReturnExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXReturnExpression(DebugInternalReactionsLanguageParser.RuleXReturnExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXReturnExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXReturnExpression(DebugInternalReactionsLanguageParser.RuleXReturnExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXTryCatchFinallyExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXTryCatchFinallyExpression(DebugInternalReactionsLanguageParser.RuleXTryCatchFinallyExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXTryCatchFinallyExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXTryCatchFinallyExpression(DebugInternalReactionsLanguageParser.RuleXTryCatchFinallyExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSynchronizedExpression}.
	 * @param ctx the parse tree
	 */
	void enterRuleXSynchronizedExpression(DebugInternalReactionsLanguageParser.RuleXSynchronizedExpressionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXSynchronizedExpression}.
	 * @param ctx the parse tree
	 */
	void exitRuleXSynchronizedExpression(DebugInternalReactionsLanguageParser.RuleXSynchronizedExpressionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCatchClause}.
	 * @param ctx the parse tree
	 */
	void enterRuleXCatchClause(DebugInternalReactionsLanguageParser.RuleXCatchClauseContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXCatchClause}.
	 * @param ctx the parse tree
	 */
	void exitRuleXCatchClause(DebugInternalReactionsLanguageParser.RuleXCatchClauseContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedName}.
	 * @param ctx the parse tree
	 */
	void enterRuleQualifiedName(DebugInternalReactionsLanguageParser.RuleQualifiedNameContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedName}.
	 * @param ctx the parse tree
	 */
	void exitRuleQualifiedName(DebugInternalReactionsLanguageParser.RuleQualifiedNameContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNumber}.
	 * @param ctx the parse tree
	 */
	void enterRuleNumber(DebugInternalReactionsLanguageParser.RuleNumberContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleNumber}.
	 * @param ctx the parse tree
	 */
	void exitRuleNumber(DebugInternalReactionsLanguageParser.RuleNumberContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmTypeReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmTypeReference(DebugInternalReactionsLanguageParser.RuleJvmTypeReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmTypeReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmTypeReference(DebugInternalReactionsLanguageParser.RuleJvmTypeReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleArrayBrackets}.
	 * @param ctx the parse tree
	 */
	void enterRuleArrayBrackets(DebugInternalReactionsLanguageParser.RuleArrayBracketsContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleArrayBrackets}.
	 * @param ctx the parse tree
	 */
	void exitRuleArrayBrackets(DebugInternalReactionsLanguageParser.RuleArrayBracketsContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXFunctionTypeRef}.
	 * @param ctx the parse tree
	 */
	void enterRuleXFunctionTypeRef(DebugInternalReactionsLanguageParser.RuleXFunctionTypeRefContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXFunctionTypeRef}.
	 * @param ctx the parse tree
	 */
	void exitRuleXFunctionTypeRef(DebugInternalReactionsLanguageParser.RuleXFunctionTypeRefContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmParameterizedTypeReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmParameterizedTypeReference(DebugInternalReactionsLanguageParser.RuleJvmParameterizedTypeReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmParameterizedTypeReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmParameterizedTypeReference(DebugInternalReactionsLanguageParser.RuleJvmParameterizedTypeReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmArgumentTypeReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmArgumentTypeReference(DebugInternalReactionsLanguageParser.RuleJvmArgumentTypeReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmArgumentTypeReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmArgumentTypeReference(DebugInternalReactionsLanguageParser.RuleJvmArgumentTypeReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmWildcardTypeReference}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmWildcardTypeReference(DebugInternalReactionsLanguageParser.RuleJvmWildcardTypeReferenceContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmWildcardTypeReference}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmWildcardTypeReference(DebugInternalReactionsLanguageParser.RuleJvmWildcardTypeReferenceContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmUpperBound}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmUpperBound(DebugInternalReactionsLanguageParser.RuleJvmUpperBoundContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmUpperBound}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmUpperBound(DebugInternalReactionsLanguageParser.RuleJvmUpperBoundContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmUpperBoundAnded}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmUpperBoundAnded(DebugInternalReactionsLanguageParser.RuleJvmUpperBoundAndedContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmUpperBoundAnded}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmUpperBoundAnded(DebugInternalReactionsLanguageParser.RuleJvmUpperBoundAndedContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmLowerBound}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmLowerBound(DebugInternalReactionsLanguageParser.RuleJvmLowerBoundContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmLowerBound}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmLowerBound(DebugInternalReactionsLanguageParser.RuleJvmLowerBoundContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmLowerBoundAnded}.
	 * @param ctx the parse tree
	 */
	void enterRuleJvmLowerBoundAnded(DebugInternalReactionsLanguageParser.RuleJvmLowerBoundAndedContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleJvmLowerBoundAnded}.
	 * @param ctx the parse tree
	 */
	void exitRuleJvmLowerBoundAnded(DebugInternalReactionsLanguageParser.RuleJvmLowerBoundAndedContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedNameWithWildcard}.
	 * @param ctx the parse tree
	 */
	void enterRuleQualifiedNameWithWildcard(DebugInternalReactionsLanguageParser.RuleQualifiedNameWithWildcardContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedNameWithWildcard}.
	 * @param ctx the parse tree
	 */
	void exitRuleQualifiedNameWithWildcard(DebugInternalReactionsLanguageParser.RuleQualifiedNameWithWildcardContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleValidID}.
	 * @param ctx the parse tree
	 */
	void enterRuleValidID(DebugInternalReactionsLanguageParser.RuleValidIDContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleValidID}.
	 * @param ctx the parse tree
	 */
	void exitRuleValidID(DebugInternalReactionsLanguageParser.RuleValidIDContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXImportSection}.
	 * @param ctx the parse tree
	 */
	void enterRuleXImportSection(DebugInternalReactionsLanguageParser.RuleXImportSectionContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXImportSection}.
	 * @param ctx the parse tree
	 */
	void exitRuleXImportSection(DebugInternalReactionsLanguageParser.RuleXImportSectionContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXImportDeclaration}.
	 * @param ctx the parse tree
	 */
	void enterRuleXImportDeclaration(DebugInternalReactionsLanguageParser.RuleXImportDeclarationContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleXImportDeclaration}.
	 * @param ctx the parse tree
	 */
	void exitRuleXImportDeclaration(DebugInternalReactionsLanguageParser.RuleXImportDeclarationContext ctx);
	/**
	 * Enter a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedNameInStaticImport}.
	 * @param ctx the parse tree
	 */
	void enterRuleQualifiedNameInStaticImport(DebugInternalReactionsLanguageParser.RuleQualifiedNameInStaticImportContext ctx);
	/**
	 * Exit a parse tree produced by {@link DebugInternalReactionsLanguageParser#ruleQualifiedNameInStaticImport}.
	 * @param ctx the parse tree
	 */
	void exitRuleQualifiedNameInStaticImport(DebugInternalReactionsLanguageParser.RuleQualifiedNameInStaticImportContext ctx);
}