from agent.Plan import *
from agent.Environment.html_env.async_env import AsyncHTMLEnvironment, ActionExecutionError
from agent.Environment.html_env.build_tree import HTMLTree
import re
import toml
import json
import traceback
import os
from agent.Environment import ActionExecutionError, create_action
from agent.Plan import Planning
from agent.Utils.utils import save_screenshot, is_valid_base64 
from agent.Reward.global_reward import GlobalReward
from agent.LLM import save_token_count_to_file, create_llm_instance
from logs import logger
from agent.Utils.format_converter import validate_and_replan_links


async def adjust_max_action_step(conditions, current_info, encountered_errors, increase_step):
    total_increase = 0
    for condition_type, keywords in conditions.items():
        for keyword in keywords:
            if keyword in current_info[condition_type] and keyword not in encountered_errors:
                print(
                    f"Detected '{keyword}' in {current_info[condition_type]}, suggesting increase by {increase_step} steps.")
                total_increase += increase_step
                encountered_errors.add(keyword)
    return total_increase, encountered_errors


def get_netloc(url: str) -> str:
    """Extract the domain name, for example, extract 'zhihu' from 'zhihu.com', extract 'google' from 'www.google.com.hk' """
    url = urlparse(url)
    try:
        if url.netloc.startswith("www"):
            netloc = re.findall(".*?\.(.*?)\..*?", url.netloc)[0]
        else:
            netloc = re.findall("(.*?)\..*?", url.netloc)[0]
    except:
        netloc = ""
    return netloc


async def parse_current_trace(response: dict, env: AsyncHTMLEnvironment, step_reward: dict):
    thought = response["description"].get("thought")
    action_type = response.get('action_type') if response.get('action_type') else ""
    
    # 根据action_type处理action_input
    if action_type == "get_final_answer":
        # 对于get_final_answer，直接获取value而不做格式限制
        acton_input = response.get('value')
    else:
        # 其他action_type保持原有的字符串格式要求
        acton_input = response['value'] if response.get('value') and isinstance(response.get('value'), str) else ""
    
    action = response["description"].get("action")
    reflection = step_reward.get("description") if step_reward else ""
    current_trace = {"thought": thought,
                     "action": action, "reflection": reflection}
    element_value = ""
    text_content = ""
    selector = None

    try:
        element_id = int(response['id'])
    except:
        element_id = 0
    
        
    if action_type in ["fill_form", "fill_search", "click", "select_option", "hover"]:
        try:
            logger.debug(f"Processing element with id: {element_id}")
            logger.debug(f"Current env.tree.nodeDict keys: {list(env.tree.nodeDict.keys())}")

            if env.mode == "vision":
                coordinates = response.get('coordinates', {"x": 0, "y": 0})
                element = await env._get_element_at_position(coordinates["x"],coordinates["y"])
                selector = element["selector"]
                element_value = element["textContent"]
            else:
                selector, xpath = env.tree.get_selector_and_xpath(
                env.tree.nodeDict[element_id])
                logger.debug(f"Got selector result: {selector}")
                
                element_value = env.tree.get_element_value(
                    env.tree.nodeDict[element_id])
                logger.debug(f"Got element value: {element_value}")
            
            if action_type in ["fill_form", "fill_search"]:
                element_value = acton_input
        except Exception as e:
            logger.error(f"Error processing element {element_id}: {str(e)}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            logger.info("Failed to obtain element_id from the accessibility tree.")
            element_id = 0
            action_type = "None"
    elif action_type in ["get_final_answer", "cache_data"]:
        selector = None
        element_id = 0
        text_content = acton_input
    elif action_type == "get_link":
        selector = None
        element_id = 0
        links = response['value'] if response.get('value') else ""
        text_content = links
    else:
        selector = None
        element_id = 0
        
    try:
        execute_action = create_action(
            elementid=element_id, action_type=action_type, action_input=str(acton_input), selector=selector)
        logger.info(f"Create action: {execute_action}")
    except Exception as e:
        logger.error(f"Create action error: {e}")
        execute_action = create_action(
            elementid=element_id, action_type="None", action_input="", selector=selector)
            
    return execute_action, current_trace, selector, element_value, text_content

def parse_current_trace_vision(response: dict, env: AsyncHTMLEnvironment, step_reward: dict):
    # 1. 基本信息提取
    thought = response.get("thought", "")
    action_type = response.get('action_type', "")
    
    # 2. 处理action输入和坐标
    action_input = response.get('action_input', "")
    
    
    # 3. 构建追踪信息
    reflection = step_reward.get("description") if step_reward else ""
    current_trace = {
        "thought": thought,
        "action": action_type, 
        "reflection": reflection
    }
    
    # 4. 初始化返回值
    text_content = ""
    
    # 5. 根据不同action_type处理
    if action_type in ["type", "fill"]:
        try:
            # 验证必要参数
            if not action_input:
                raise ValueError("action_input is required for type/fill action")
            if not (isinstance(coordinates['x'], (int, float)) and isinstance(coordinates['y'], (int, float))):
                raise ValueError("Valid coordinates are required for type/fill action")
                
            text_content = action_input
            
        except Exception as e:
            logger.error(f"Error processing type/fill action: {str(e)}")
            action_type = "None"
            coordinates = {"x": 0, "y": 0}
            
    elif action_type in ["click", "double_click", "right_click", "mouse_move", "left_click_drag"]:
        try:
            # 验证坐标
            if not (isinstance(coordinates['x'], (int, float)) and isinstance(coordinates['y'], (int, float))):
                raise ValueError(f"Valid coordinates are required for {action_type}")
                
        except Exception as e:
            logger.error(f"Error processing click action: {str(e)}")
            action_type = "None"
            coordinates = {"x": 0, "y": 0}
            
    elif action_type in ["get_final_answer", "cache_data"]:
        coordinates = {"x": 0, "y": 0}
        text_content = action_input
        
    elif action_type == "screenshot":
        coordinates = {"x": 0, "y": 0}
        
    else:
        # 默认情况
        action_type = "None"
        coordinates = {"x": 0, "y": 0}
    
    # 6. 创建执行动作
    try:
        execute_action = create_vision_action(
            action_type=action_type,
            coordinates=coordinates,
            action_input=str(action_input) if action_input else ""
        )
    except Exception as e:
        logger.error(f"Create vision action error: {e}")
        execute_action = create_vision_action(
            action_type="None",
            coordinates={"x": 0, "y": 0},
            action_input=""
        )
    
    return execute_action, current_trace, coordinates, text_content

def create_vision_action(action_type: str, coordinates: dict, action_input: str = ""):
    """
    创建视觉模式下的执行动作
    
    Args:
        action_type: 动作类型
        coordinates: 坐标信息 {"x": x, "y": y}
        action_input: 输入文本(可选)
        
    Returns:
        包含动作信息的字典
    """
    return {
        "action_type": action_type,
        "coordinates": coordinates,
        "action_input": action_input
    }

def read_config(toml_path=None):
    """
    Reads a TOML configuration file from the given path or the default path
    and returns its content as a dictionary.

    Args:
        toml_path (str, optional): The path to the TOML configuration file.
                                           If None, use the default path.

    Returns:
        dict: The content of the configuration file.
    """
    if toml_path is None:
        # default_path = os.path.join(os.path.dirname(__file__), 'default_settings.toml')
        toml_path = 'configs/setting.toml'

    with open(toml_path, 'r') as f:
        config = toml.load(f)

    return config


async def run_task(
        mode,
        task_mode,
        task_name,
        task_uuid,
        config,
        write_result_file_path,
        reference_task_length,
        env,
        global_reward_mode,
        global_reward_text_model,
        planning_model,
        ground_truth_mode,
        ground_truth_data,
        interaction_mode,
        record_time=None,
        output_parameters=None,
        response_type=None
):
    # await env.reset("https://www.google.com/")
    # await env.reset("https://www.ycombinator.com/launches")
    # await env.reset("https://www.xiaohongshu.com/explore")
    await env.reset("https://www.ctrip.com/")
    response_error_count = 0
    response_total_count = 0
    vision_reward = None

    # Related to the HTML environment
    observation = await env.get_obs()
    observation_VforD = ""
    error_description = ""
    previous_trace = []

    # Related to response
    out_put = None
    invalid_vision_reward_num = 0

    # If all are matched, the task is completed
    task_finished = False
    task_global_status = ""
    human_interaction_stop_status = False

    # Configuration related to controlling the length of steps
    conditions = config["conditions"]
    increase_step = config["steps"]["batch_tasks_condition_step_increase"]
    encountered_errors = set()
    current_info = {"URL": env.page.url}
    num_steps = 0
    step_index = 0
    if task_mode == "single_task":
        max_steps = int(reference_task_length)
    elif task_mode == "batch_tasks":
        max_steps = int(
            max(config['steps']['batch_tasks_max_action_step'], 1.5 * reference_task_length))
    additional_steps = 0

    # Store the results of the planning process for a task
    task_result = {}
    task_result["task_name"] = task_name
    task_result["id"] = task_uuid
    task_result["reference_task_length"] = reference_task_length
    steps_list = []
    
    evaluate_steps = []  

    # Store the token counts of each step
    steps_token_counts = 0
    step_tokens = {"steps_tokens_record": [], "steps_token_counts": steps_token_counts}
    steps_planning_input_token_counts = 0
    steps_reward_input_token_counts = 0
    steps_planning_output_token_counts = 0
    steps_reward_output_token_counts = 0
    steps_input_token_counts = 0
    steps_output_token_counts = 0
    token_counts_filename = f"token_results/token_counts_{record_time}_{planning_model}_{global_reward_text_model}.json"
    final_answer = None
    while num_steps < max_steps + additional_steps:
        error_message = ""
        total_step_score = 0
        step_reward = {}
        status_description = ""
        planning_input_token_count = 0
        planning_output_token_count = 0
        reward_token_count = [0, 0]

        logger.info(
            "**🤖 The agent is in the process of starting planning 🤖**")

        if global_reward_mode != 'no_global_reward' and len(previous_trace) > 0:
            step_reward, status_description, reward_token_count = await GlobalReward.evaluate(
                config=config,
                model_name=global_reward_text_model,
                user_request=task_name,
                previous_trace=previous_trace,
                observation=observation,
                current_info=current_info,
                task_name_id=task_uuid,
                global_reward_mode=global_reward_mode,
                ground_truth_mode=ground_truth_mode,
                ground_truth_data=ground_truth_data,
            )

        for _ in range(3):
            response_total_count += 1
            try:
                out_put = await Planning.plan(
                    config=config,
                    user_request=task_name,
                    model_name=planning_model,
                    previous_trace=previous_trace,
                    observation=observation,
                    feedback=error_description,
                    mode=mode,
                    observation_VforD=observation_VforD,
                    status_description=status_description
                )

                if out_put is not None:
                    break
            except Exception as e:
                out_put = None
                response_error_count += 1
                traceback.print_exc()
                continue

        if out_put:
            planning_input_token_count += out_put.get("planning_token_count", [0, 0])[0]
            planning_output_token_count += out_put.get("planning_token_count", [0, 0])[1]
            each_step_dict = {}
            each_step_dict["step_index"] = step_index
            each_step_dict["dict_result"] = out_put

            execute_action, current_trace, path, element_value, text_content = await parse_current_trace(
                out_put, env, step_reward)
            selector, xpath = (
                path[0], path[1]) if path is not None else (None, None)
            each_step_dict["selector"] = selector
            each_step_dict["element_value"] = element_value

            each_step_dict["current_trace"] = current_trace
            each_step_dict["execute_action"] = execute_action
            each_step_dict["text_content"] = text_content

            logger.info(f"-- Planning output: {out_put}")
            logger.info(f"-- Current trace: {current_trace}")
            logger.info(f"-- Action: {execute_action}")

            logger.info(f"-- Selector: {selector}")
            logger.info(f"-- Element value: {element_value}")
            

            logger.info(
                "**🤖 The agent is in the process of executing the action 🤖**")

            if out_put.get("action_type") not in ["get_final_answer"]:
                try:
                    await env.execute_action(execute_action)
                    previous_trace.append(current_trace)
                    error_description = ""
                    logger.info("-- Successfully execute the action ")
                except ActionExecutionError as ee:
                    error_message = ee.message
                    logger.info("-- Failed to execute the action")
                    logger.error(
                        f"ActionExecutionError occurred: {error_message}")
                error_description = error_message

                if mode in ["d_v", "dom_v_desc", "vision_to_dom"]:
                    observation, observation_VforD = await env.get_obs()
                    save_screenshot(mode=mode, record_time=record_time, task_name=task_name,
                                    step_number=num_steps, description="obs", screenshot_base64=observation_VforD)
                else:
                    observation = await env.get_obs()
                    if mode == "vision":
                        save_screenshot(mode=mode, record_time=record_time, task_name=task_name,
                                    step_number=num_steps, description="obs", screenshot_base64=observation)


                # URL after executing the action
                each_step_dict["step_url"] = env.page.url
                each_step_dict["step_url"] = env.page.url
                each_step_dict["error_message"] = error_message
                each_step_dict["previous_trace"] = str(previous_trace)

                logger.info(
                    f"-- The URL is: {env.page.url}")

                if "vision" in global_reward_mode:
                    vision_reward = await env.capture()
                    save_screenshot(mode=mode, record_time=record_time, task_name=task_name,
                                    step_number=num_steps, description="reward",
                                    screenshot_base64=vision_reward, task_uuid=task_uuid)
                    is_valid, message = is_valid_base64(vision_reward)
                    if not is_valid:
                        invalid_vision_reward_num += 1

                current_info = {
                    "URL": env.page.url
                }
                if vision_reward:
                    current_info.update({"vision_reward": vision_reward})
                logger.info(
                    f"**🤖 Time Step: {num_steps + 1}, Total steps: {max_steps + additional_steps} 🤖**")
                step_increase, encountered_errors = await adjust_max_action_step(
                    conditions, current_info, encountered_errors, increase_step)
                additional_steps += step_increase
                steps_list.append(each_step_dict)
                step_index += 1
                if num_steps >= 25 or task_global_status == "finished" or task_finished:
                    break
            
            if out_put.get("action_type") in ["get_final_answer"]:
                logger.info("**Task completed with final answer.**")
                logger.info(f"raw final answer is {text_content}")
                validated_content = await validate_and_replan_links(
                    text_content,
                    observation,
                    task_name,
                    output_parameters,
                    response_type,
                    env.page.url if env.page else None
                )
                logger.info(f"validated final answer is {validated_content}")
                processed_answer = process_final_answer(validated_content, env.tree)
                final_answer = processed_answer
                logger.info(f"Final answer type: {type(final_answer)}")
                
                planning_token_count_number = planning_input_token_count + planning_output_token_count
                reward_token_count_number = reward_token_count[0] + reward_token_count[1]
                step_input_token_count = planning_input_token_count + reward_token_count[0]
                step_output_token_count = planning_output_token_count + reward_token_count[1]
                step_token_count = planning_token_count_number + reward_token_count_number
                single_step_tokens = {
                    "planning_input_token_count": planning_input_token_count,
                    "planning_output_token_count": planning_output_token_count,
                    "planning_token_count": planning_token_count_number,
                    "reward_input_token_count": reward_token_count[0],
                    "reward_output_token_count": reward_token_count[1],
                    "reward_token_count": reward_token_count_number,
                    "input_token_count": step_input_token_count,
                    "output_token_count": step_output_token_count,
                    "token_count": step_token_count
                }

                step_tokens["steps_tokens_record"].append(single_step_tokens)

                steps_planning_input_token_counts += planning_input_token_count
                steps_planning_output_token_counts += planning_output_token_count
                steps_reward_input_token_counts += reward_token_count[0]
                steps_reward_output_token_counts += reward_token_count[1]
                steps_input_token_counts += step_input_token_count
                steps_output_token_counts += step_output_token_count
                steps_token_counts += step_token_count

                step_tokens["steps_planning_input_token_counts"] = steps_planning_input_token_counts
                step_tokens["steps_planning_output_token_counts"] = steps_planning_output_token_counts
                step_tokens["steps_reward_input_token_counts"] = steps_reward_input_token_counts
                step_tokens["steps_reward_output_token_counts"] = steps_reward_output_token_counts
                step_tokens["steps_input_token_counts"] = steps_input_token_counts
                step_tokens["steps_output_token_counts"] = steps_output_token_counts
                step_tokens["steps_token_counts"] = steps_token_counts

                save_token_count_to_file(token_counts_filename, step_tokens, task_name, global_reward_text_model,
                                        planning_model, config["token_pricing"])
                
                logger.info(f"**final answer is {str(final_answer)}**")
                return final_answer
            
            
        
        num_steps += 1
        if interaction_mode:
            logger.info(
                "Press Enter to proceed to the next action, or type 'q' to quit the task. If you encounter any unexpected issues such as network connection errors or captcha challenges, please resolve them manually now.")
            a = input()
            if a.lower() == "q":
                logger.info("User requested to quit the program.")
                human_interaction_stop_status = True
                break

        planning_token_count_number = planning_input_token_count + planning_output_token_count
        reward_token_count_number = reward_token_count[0] + reward_token_count[1]
        step_input_token_count = planning_input_token_count + reward_token_count[0]
        step_output_token_count = planning_output_token_count + reward_token_count[1]
        step_token_count = planning_token_count_number + reward_token_count_number
        single_step_tokens = {
            "planning_input_token_count": planning_input_token_count,
            "planning_output_token_count": planning_output_token_count,
            "planning_token_count": planning_token_count_number,
            "reward_input_token_count": reward_token_count[0],
            "reward_output_token_count": reward_token_count[1],
            "reward_token_count": reward_token_count_number,
            "input_token_count": step_input_token_count,
            "output_token_count": step_output_token_count,
            "token_count": step_token_count
        }

        step_tokens["steps_tokens_record"].append(single_step_tokens)

        steps_planning_input_token_counts += planning_input_token_count
        steps_planning_output_token_counts += planning_output_token_count
        steps_reward_input_token_counts += reward_token_count[0]
        steps_reward_output_token_counts += reward_token_count[1]
        steps_input_token_counts += step_input_token_count
        steps_output_token_counts += step_output_token_count
        steps_token_counts += step_token_count

    step_tokens["steps_planning_input_token_counts"] = steps_planning_input_token_counts
    step_tokens["steps_planning_output_token_counts"] = steps_planning_output_token_counts
    step_tokens["steps_reward_input_token_counts"] = steps_reward_input_token_counts
    step_tokens["steps_reward_output_token_counts"] = steps_reward_output_token_counts
    step_tokens["steps_input_token_counts"] = steps_input_token_counts
    step_tokens["steps_output_token_counts"] = steps_output_token_counts
    step_tokens["steps_token_counts"] = steps_token_counts

    save_token_count_to_file(token_counts_filename, step_tokens, task_name, global_reward_text_model,
                             planning_model, config["token_pricing"])
    
    
    # 如果到这里还没有 return，说明任务未完成
    execution_summary = await summarize_execution_steps(
        steps_list, 
        task_name,
        planning_model
    )
    
    result = {
        "status": "incomplete",
        "execution_summary": execution_summary,
        "steps_taken": len(steps_list),
        "max_steps_allowed": max_steps + additional_steps,
        "task_name": task_name,
        "task_uuid": task_uuid,
        "last_url": env.page.url if env.page else None
    }
    
    # 保存结果到文件
    json_result_folder = write_result_file_path
    if not os.path.exists(json_result_folder):
        os.makedirs(json_result_folder)
    
    json_out_file_path = os.path.join(
        json_result_folder, f"{task_uuid}_incomplete.json")
    
    logger.info(f"Writing incomplete task results to: {json_out_file_path}")
    with open(json_out_file_path, 'w') as json_file:
        json.dump(result, json_file)
    
    return result


async def summarize_execution_steps(steps_list: list, task_name: str, planning_text_model: str) -> str:
    """使用已有的 LLM 实例来总结执行步骤"""
    try:
        # 构建步骤摘要
        steps_summary = []
        for step in steps_list:
            if 'current_trace' in step:
                trace = step['current_trace']
                step_info = {
                    'thought': trace.get('thought', ''),
                    'action': trace.get('action', ''),
                    'error': step.get('error_message', '')
                }
                steps_summary.append(step_info)
        
        # 构建提示信息
        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant analyzing web automation execution steps. Please provide a concise summary."
            },
            {
                "role": "user",
                "content": f"""Task: {task_name}
Please analyze these execution steps and summarize/inference the main issues:

Steps:
{json.dumps(steps_summary, indent=2)}

Provide a concise summary focusing on:
1. What was attempted
2. What problems were encountered
3. Why the task might have failed
"""
            }
        ]

        # 使用现有的 LLM 实例
        llm = create_llm_instance(planning_text_model)
        summary, _ = await llm.request(messages=messages, temperature=0.3)
        return summary

    except Exception as e:
        logger.error(f"Error in summarizing steps: {e}")
        return "Failed to generate summary due to error."

def process_final_answer(final_answer: str | list | dict, html_tree: HTMLTree) -> str:
    """Process final answer to resolve any link IDs"""
    try:
        # Handle JSON string that starts with ```json
        if isinstance(final_answer, str):
            # Remove markdown code block syntax if present
            if final_answer.startswith('```'):
                final_answer = '\n'.join(final_answer.split('\n')[1:-1])
            
        # Convert final_answer to dict if it's already a Python object
        if isinstance(final_answer, (list, dict)):
            answer_dict = final_answer
        else:
            # Parse the final answer if it's a string
            answer_dict = json.loads(final_answer)
        
        def extract_number(value: str | int) -> int | None:
            """Extract the first number from a string or return the number itself"""
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                numbers = re.findall(r'\d+', value)
                return int(numbers[0]) if numbers else None
            return None
        
        # Recursively process dictionary to find and resolve link IDs
        def resolve_links(obj):
            """Recursively process dictionary to find and resolve link IDs with href values"""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if 'link' in key.lower() or 'url' in key.lower():
                        # Handle single link ID
                        if isinstance(value, (int, str)):
                            link_id = extract_number(value)
                            if link_id and link_id in html_tree.link_index:
                                # 只替换href值，保持其他键值不变
                                result[key] = html_tree.link_index[link_id]['href']
                            else:
                                result[key] = None
                        # Handle array of link IDs
                        elif isinstance(value, list):
                            result[key] = [
                                html_tree.link_index[extract_number(id)]['href']
                                if extract_number(id) and extract_number(id) in html_tree.link_index
                                else None
                                for id in value
                            ]
                        else:
                            result[key] = value
                    else:
                        # Recursively process nested values
                        result[key] = resolve_links(value)
                return result
            elif isinstance(obj, list):
                # Process each item in the list
                return [resolve_links(item) for item in obj]
            return obj
        
        processed_answer = resolve_links(answer_dict)
        return json.dumps(processed_answer, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error processing final answer: {e}")
        # If there's any error in processing, return the original as a JSON string
        if isinstance(final_answer, str):
            # Remove markdown code block syntax if present
            if final_answer.startswith('```'):
                final_answer = '\n'.join(final_answer.split('\n')[1:-1])
        return json.dumps(final_answer) if isinstance(final_answer, (list, dict)) else str(final_answer)
