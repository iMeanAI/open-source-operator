import asyncio
import logging
from app import load_config, setup_logging, run_inference

async def test_acl_submission():
    """Test function to directly test the inference pipeline"""
    try:
        # Test parameters
        instruction = "Find paper submission dates of ACL2025"
        mode = "dom"  # Using DOM mode as default
        
        # Load config to get the default model
        config = load_config()
        model = config['model']['selected']
        
        # Setup logging
        setup_logging(config)
        logging.info(f"Starting test with instruction: {instruction}")
        
        # Run the inference
        result = await run_inference(instruction, mode, model)
        print("\n=== Test Results ===")
        print(f"Instruction: {instruction}")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        logging.error(f"Test error: {str(e)}")

async def test_travel_info():
    """Test function to directly test the inference pipeline"""
    try:
        # Test parameters
        instruction = "我希望知道达拉斯机场的君悦酒店具体在机场内部怎么走？"
        mode = "vision"  # Using DOM mode as default
        
        # Load config to get the default model
        config = load_config()
        model = config['model']['selected']
        
        # Setup logging
        setup_logging(config)
        logging.info(f"Starting test with instruction: {instruction}")
        
        # Run the inference
        result = await run_inference(instruction, mode, model)
        print("\n=== Test Results ===")
        print(f"Instruction: {instruction}")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        logging.error(f"Test error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_acl_submission()) 