from collections import defaultdict
from typing import List, Dict, Any, Optional
# import xgboost as xgb
from utility.logger import setup_logger
from utility.utils import get_current_timestamp

logger = setup_logger(__name__)

class XGBoostAggregator:
    """Enhanced XGBoost model aggregator with comprehensive logging"""
    
    def __init__(self):
        logger.info("Initializing XGBoost aggregator")
        self.aggregation_stats = {
            'total_rounds': 0,
            'successful_aggregations': 0,
            'failed_aggregations': 0
        }
    
    def aggregate_weights_bagging(self, client_weights_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Aggregate XGBoost model weights using bagging method with detailed logging
        """
        logger.info(f"Starting bagging aggregation for {len(client_weights_list)} clients")
        
        if not client_weights_list:
            logger.error("No client weights provided for aggregation")
            self.aggregation_stats['failed_aggregations'] += 1
            return None
        
        try:
            # Initialize aggregated structure
            aggregated_weights = {
                'trees': [],
                'feature_importance': defaultdict(float),
                'config': None,
                'num_boosted_rounds': 0,
                'num_features': 0,
                'client_contributions': [],
                'aggregation_metadata': {
                    'method': 'bagging',
                    'timestamp': get_current_timestamp(),
                    'num_clients': len(client_weights_list)
                }
            }
            
            total_trees = 0
            valid_clients = 0
            
            logger.debug("Processing client weights...")
            
            # Process each client's weights
            for client_idx, client_weights in enumerate(client_weights_list):
                if client_weights is None:
                    logger.warning(f"Client {client_idx + 1} provided null weights, skipping")
                    continue
                
                client_trees = client_weights.get('trees', [])
                client_importance = client_weights.get('feature_importance', {})
                client_features = client_weights.get('num_features', 0)
                
                logger.info(f"Client {client_idx + 1}: {len(client_trees)} trees, {client_features} features")
                
                if not client_trees:
                    logger.warning(f"Client {client_idx + 1} has no trees, skipping")
                    continue
                
                valid_clients += 1
                
                # Add trees with metadata
                for tree_idx, tree in enumerate(client_trees):
                    tree_with_meta = {
                        'tree_structure': tree,
                        'client_id': client_idx + 1,
                        'original_tree_id': tree_idx
                    }
                    aggregated_weights['trees'].append(tree_with_meta)
                    total_trees += 1
                
                # Aggregate feature importance
                for feature, importance in client_importance.items():
                    aggregated_weights['feature_importance'][feature] += importance / len(client_weights_list)
                    logger.debug(f"Feature {feature}: importance {importance}")
                
                # Use first valid client's configuration
                if aggregated_weights['config'] is None and client_weights.get('config'):
                    aggregated_weights['config'] = client_weights['config']
                    logger.debug("Using configuration from first valid client")
                
                # Track client contributions
                contribution = {
                    'client_id': client_idx + 1,
                    'num_trees': len(client_trees),
                    'num_features': client_features
                }
                aggregated_weights['client_contributions'].append(contribution)
                logger.debug(f"Client {client_idx + 1} contribution: {contribution}")
            
            if valid_clients == 0:
                logger.error("No valid clients found during aggregation")
                self.aggregation_stats['failed_aggregations'] += 1
                return None
            
            # Update final metadata
            aggregated_weights['num_boosted_rounds'] = total_trees
            aggregated_weights['num_features'] = max([
                cw.get('num_features', 0) for cw in client_weights_list if cw
            ], default=0)
            
            # Log aggregation summary
            logger.info("Bagging aggregation completed successfully")
            logger.info(f"  - Valid clients: {valid_clients}/{len(client_weights_list)}")
            logger.info(f"  - Total trees in ensemble: {total_trees}")
            logger.info(f"  - Features: {aggregated_weights['num_features']}")
            logger.info(f"  - Client tree contributions: {[c['num_trees'] for c in aggregated_weights['client_contributions']]}")
            
            self.aggregation_stats['successful_aggregations'] += 1
            self.aggregation_stats['total_rounds'] += 1
            
            return aggregated_weights
            
        except Exception as e:
            logger.error(f"Error during bagging aggregation: {e}", exc_info=True)
            self.aggregation_stats['failed_aggregations'] += 1
            return None
    
    def get_aggregation_stats(self) -> Dict[str, int]:
        """Get aggregation statistics"""
        logger.debug(f"Aggregation stats requested: {self.aggregation_stats}")
        return self.aggregation_stats.copy()
