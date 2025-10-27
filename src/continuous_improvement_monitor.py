#!/usr/bin/env python3
"""
Continuous Improvement Monitor - Monitor and track continuous optimization
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging
import time
import os
import threading

logger = logging.getLogger(__name__)

class ContinuousImprovementMonitor:
    """Monitor continuous improvement and optimization"""
    
    def __init__(self):
        self.improvement_history = []
        self.optimization_status = {}
        self.performance_trends = {}
        self.monitoring_active = True
        
    def start_monitoring(self):
        """Start continuous monitoring"""
        logger.info("Starting continuous improvement monitoring")
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor_optimization)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return monitor_thread
    
    def _monitor_optimization(self):
        """Monitor optimization progress"""
        while self.monitoring_active:
            try:
                # Check optimization progress files
                self._check_optimization_progress()
                
                # Update performance trends
                self._update_performance_trends()
                
                # Generate improvement report
                self._generate_improvement_report()
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring: {e}")
                time.sleep(60)
    
    def _check_optimization_progress(self):
        """Check optimization progress files"""
        progress_files = [
            'reports/evolutionary_optimization_progress.json',
            'reports/hyperparameter_tuning_progress.json',
            'reports/continuous_optimization_progress.json'
        ]
        
        for file_path in progress_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        progress = json.load(f)
                    
                    # Extract improvement data
                    improvement = {
                        'timestamp': datetime.now().isoformat(),
                        'file': file_path,
                        'best_score': progress.get('best_score', 0),
                        'generation': progress.get('generation', 0),
                        'iteration': progress.get('iteration', 0)
                    }
                    
                    self.improvement_history.append(improvement)
                    
                except Exception as e:
                    logger.error(f"Error reading {file_path}: {e}")
    
    def _update_performance_trends(self):
        """Update performance trends"""
        if not self.improvement_history:
            return
        
        # Calculate trends
        recent_improvements = self.improvement_history[-10:]  # Last 10 improvements
        
        if len(recent_improvements) >= 2:
            # Calculate improvement rate
            scores = [imp['best_score'] for imp in recent_improvements]
            improvement_rate = (scores[-1] - scores[0]) / len(scores) if len(scores) > 1 else 0
            
            # Update trends
            self.performance_trends = {
                'improvement_rate': improvement_rate,
                'recent_scores': scores,
                'trend_direction': 'improving' if improvement_rate > 0 else 'plateauing',
                'last_update': datetime.now().isoformat()
            }
    
    def _generate_improvement_report(self):
        """Generate improvement report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'monitoring_duration': self._calculate_monitoring_duration(),
            'total_improvements': len(self.improvement_history),
            'performance_trends': self.performance_trends,
            'optimization_status': self.optimization_status,
            'recommendations': self._generate_recommendations()
        }
        
        # Save report
        with open('reports/continuous_improvement_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("Improvement report generated")
    
    def _calculate_monitoring_duration(self):
        """Calculate monitoring duration"""
        if not self.improvement_history:
            return 0
        
        start_time = datetime.fromisoformat(self.improvement_history[0]['timestamp'])
        current_time = datetime.now()
        duration = (current_time - start_time).total_seconds() / 3600  # Hours
        
        return duration
    
    def _generate_recommendations(self):
        """Generate optimization recommendations"""
        recommendations = []
        
        if not self.performance_trends:
            return recommendations
        
        # Analyze trends
        improvement_rate = self.performance_trends.get('improvement_rate', 0)
        trend_direction = self.performance_trends.get('trend_direction', 'unknown')
        
        if improvement_rate > 0.01:
            recommendations.append("Continue optimization - good improvement rate")
        elif improvement_rate > 0:
            recommendations.append("Optimization showing slow improvement - consider parameter adjustment")
        else:
            recommendations.append("Optimization plateaued - consider new strategies or parameters")
        
        if trend_direction == 'plateauing':
            recommendations.append("Consider increasing mutation rate or population size")
        
        if len(self.improvement_history) > 100:
            recommendations.append("Long optimization session - consider saving best parameters")
        
        return recommendations
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        logger.info("Monitoring stopped")
    
    def get_optimization_status(self):
        """Get current optimization status"""
        return {
            'monitoring_active': self.monitoring_active,
            'total_improvements': len(self.improvement_history),
            'performance_trends': self.performance_trends,
            'monitoring_duration': self._calculate_monitoring_duration()
        }

def main():
    """Test the continuous improvement monitor"""
    logger.info("Testing continuous improvement monitor")
    
    monitor = ContinuousImprovementMonitor()
    
    # Start monitoring
    monitor_thread = monitor.start_monitoring()
    
    # Let it run for a bit
    time.sleep(60)
    
    # Get status
    status = monitor.get_optimization_status()
    print(f"Monitoring status: {status}")
    
    # Stop monitoring
    monitor.stop_monitoring()

if __name__ == "__main__":
    main()
