#!/usr/bin/env python3
"""
AI RADAR — Personal AI Intelligence System
Main entry point for the daily digest pipeline.

Usage:
    python app.py                    # Run full pipeline
    python app.py --phase 1          # Run specific phase (collect only)
    python app.py --help             # Show options
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/radar.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='AI RADAR — Automated daily AI/tech digest'
    )
    parser.add_argument(
        '--phase',
        type=int,
        choices=range(1, 16),
        help='Run specific phase (1-15) instead of full pipeline'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test mode (no file writes, no API calls)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info('=' * 60)
    logger.info(f'🎯 AI RADAR Started at {datetime.now().isoformat()}')
    logger.info('=' * 60)

    try:
        if args.phase:
            logger.info(f'Running Phase {args.phase}...')
            # TODO: Import and run phase-specific logic
            logger.warning(f'Phase {args.phase} not yet implemented')
        else:
            logger.info('Running full pipeline (Phases 1-12)...')
            # TODO: Import and run all phases
            logger.warning('Full pipeline not yet implemented')

        logger.info('✓ Pipeline completed successfully')
        return 0

    except Exception as e:
        logger.error(f'✗ Pipeline failed: {e}', exc_info=True)
        return 1

    finally:
        logger.info('=' * 60)
        logger.info(f'🎯 AI RADAR Finished at {datetime.now().isoformat()}')
        logger.info('=' * 60)


if __name__ == '__main__':
    sys.exit(main())
