# Enhanced version of your current global_model.py with basic persistence
import json
import pickle
import os
from typing import Dict, Any, Optional
from utility.logger import setup_logger
from utility.utils import get_current_timestamp

logger = setup_logger(__name__)

class GlobalModelManager:
    """Global model manager with persistence"""
    
    def __init__(self, model_save_path: str = "global_model_latest.json"):
        logger.info("Initializing Global Model Manager with persistence")
        self.model_save_path = model_save_path
        self.current_model = None
        self.model_history = []
        self.round_number = 0
        
        # Try to load existing model
        self._load_existing_model()
    
    def _load_existing_model(self):
        """Load existing global model if it exists"""
        try:
            if os.path.exists(self.model_save_path):
                with open(self.model_save_path, 'r') as f:
                    saved_data = json.load(f)
                
                self.current_model = saved_data.get('current_model')
                self.model_history = saved_data.get('model_history', [])
                self.round_number = saved_data.get('round_number', 0)
                
                if self.current_model:
                    weights = self.current_model.get('aggregated_weights', {})
                    logger.info(f"Loaded existing global model:")
                    logger.info(f"  - Round: {self.round_number}")
                    logger.info(f"  - Trees: {len(weights.get('trees', []))}")
                    logger.info(f"  - Features: {weights.get('num_features', 0)}")
                else:
                    logger.info("No existing global model found in saved file")
            else:
                logger.info("No saved model file found - starting fresh")
                
        except Exception as e:
            logger.error(f"Error loading existing model: {e}")
            logger.info("Starting with fresh model")
    
    def _save_model(self):
        """Save current model state to disk"""
        try:
            save_data = {
                'current_model': self.current_model,
                'model_history': self.model_history,
                'round_number': self.round_number,
                'last_saved': get_current_timestamp()
            }
            
            with open(self.model_save_path, 'w') as f:
                json.dump(save_data, f, indent=2)
            
            logger.info(f"Global model saved to {self.model_save_path}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def create_ensemble_model(self, aggregated_weights: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create ensemble model from aggregated weights with persistence
        """
        logger.info(f"Creating ensemble model for round {self.round_number + 1}")
        
        if not aggregated_weights:
            logger.error("No aggregated weights provided for ensemble creation")
            return None
        
        try:
            # If we have an existing model, blend with new weights
            if self.current_model is not None:
                logger.info("Blending with existing global model...")
                aggregated_weights = self._simple_blend(aggregated_weights)
            
            # Log model statistics
            num_trees = len(aggregated_weights.get('trees', []))
            num_clients = len(aggregated_weights.get('client_contributions', []))
            num_features = aggregated_weights.get('num_features', 0)
            
            logger.info(f"Ensemble model stats:")
            logger.info(f"  - Trees: {num_trees}")
            logger.info(f"  - Contributing clients: {num_clients}")
            logger.info(f"  - Features: {num_features}")
            
            # Create ensemble structure
            ensemble_model = {
                'model_type': 'persistent_xgb_ensemble',
                'round_number': self.round_number + 1,
                'aggregated_weights': aggregated_weights,
                'ensemble_info': {
                    'total_trees': num_trees,
                    'num_clients': num_clients,
                    'aggregation_method': 'bagging_with_persistence',
                    'creation_timestamp': get_current_timestamp(),
                    'is_incremental': self.current_model is not None
                }
            }
            
            # Store model history
            model_summary = {
                'round': self.round_number + 1,
                'num_trees': num_trees,
                'num_clients': num_clients,
                'timestamp': ensemble_model['ensemble_info']['creation_timestamp'],
                'is_incremental': self.current_model is not None
            }
            self.model_history.append(model_summary)
            
            self.current_model = ensemble_model
            self.round_number += 1
            
            # Save to disk
            self._save_model()
            
            logger.info(f"Persistent ensemble model created for round {self.round_number}")
            logger.debug(f"Model history: {len(self.model_history)} rounds")
            
            return ensemble_model
            
        except Exception as e:
            logger.error(f"Error creating ensemble model: {e}", exc_info=True)
            return None
    
    def _simple_blend(self, new_weights: Dict[str, Any]) -> Dict[str, Any]:
        """Simple blending of new weights with existing model"""
        try:
            existing_weights = self.current_model['aggregated_weights']
            
            # Combine trees (limit to prevent unlimited growth)
            existing_trees = existing_weights.get('trees', [])
            new_trees = new_weights.get('trees', [])
            
            # Keep existing trees with reduced weight + add new trees
            max_total_trees = 100  # Limit total trees
            
            if len(existing_trees) + len(new_trees) > max_total_trees:
                # Keep most recent existing trees
                keep_existing = max_total_trees - len(new_trees)
                existing_trees = existing_trees[-keep_existing:] if keep_existing > 0 else []
            
            combined_trees = existing_trees + new_trees
            
            # Blend feature importance
            existing_importance = existing_weights.get('feature_importance', {})
            new_importance = new_weights.get('feature_importance', {})
            
            blended_importance = {}
            all_features = set(existing_importance.keys()) | set(new_importance.keys())
            
            for feature in all_features:
                existing_val = existing_importance.get(feature, 0.0) * 0.7  # Decay existing
                new_val = new_importance.get(feature, 0.0)
                blended_importance[feature] = existing_val + new_val
            
            # Create blended result
            blended_weights = {
                'trees': combined_trees,
                'feature_importance': blended_importance,
                'config': new_weights.get('config', existing_weights.get('config', {})),
                'num_boosted_rounds': len(combined_trees),
                'num_features': max(existing_weights.get('num_features', 0), 
                                  new_weights.get('num_features', 0)),
                'client_contributions': (existing_weights.get('client_contributions', []) + 
                                       new_weights.get('client_contributions', [])),
                'aggregation_metadata': {
                    'method': 'simple_blend',
                    'timestamp': get_current_timestamp(),
                    'existing_trees': len(existing_trees),
                    'new_trees': len(new_trees),
                    'total_trees': len(combined_trees)
                }
            }
            
            logger.info(f"Simple blend: {len(existing_trees)} existing + {len(new_trees)} new = {len(combined_trees)} total")
            return blended_weights
            
        except Exception as e:
            logger.error(f"Error in simple blend: {e}")
            return new_weights
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get current model information"""
        info = {
            'current_round': self.round_number,
            'has_current_model': self.current_model is not None,
            'history_length': len(self.model_history),
            'is_persistent': True,
            'save_path': self.model_save_path
        }
        logger.debug(f"Model info requested: {info}")
        return info
    
    def serialize_model(self, model: Dict[str, Any]) -> bytes:
        """Serialize model with logging"""
        try:
            logger.debug("Serializing model for transmission")
            serialized = pickle.dumps(model)
            size_mb = len(serialized) / (1024 * 1024)
            logger.info(f"Model serialized: {size_mb:.2f}MB")
            return serialized
        except Exception as e:
            logger.error(f"Error serializing model: {e}", exc_info=True)
            raise
