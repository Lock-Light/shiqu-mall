package org.javaup.controller;

import cn.hutool.core.bean.BeanUtil;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.springframework.beans.factory.annotation.Autowired;
import lombok.Data;
import org.javaup.dto.*;
import org.javaup.entity.*;
import org.javaup.service.*;
import org.javaup.toolkit.SnowflakeIdGenerator;
import org.javaup.utils.UserHolder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDate;
import java.util.*;

/** Local implementation: editable profiles, real connection counts and own orders. */
@RestController
public class UserProfileController {
    @Autowired private IUserService users;
    @Autowired private IUserInfoService infos;
    @Autowired private IFollowService follows;
    @Autowired private IVoucherOrderService orders;
    @Autowired private IVoucherService vouchers;
    @Autowired private SnowflakeIdGenerator ids;

    @Data public static class ProfileForm {
        private String nickName,icon,city,introduce;
        private Boolean gender;
        private LocalDate birthday;
    }

    @GetMapping("/user/profile/{id}")
    public Result profile(@PathVariable("id") Long id) {
        User user=users.getById(id);
        if(user==null)return Result.fail("用户不存在");
        UserInfo info=infos.lambdaQuery().eq(UserInfo::getUserId,id).one();
        Map<String,Object> data=new LinkedHashMap<>();
        data.put("id",id);data.put("nickName",user.getNickName());data.put("icon",user.getIcon());
        if(info!=null){data.put("city",info.getCity());data.put("introduce",info.getIntroduce());data.put("gender",info.getGender());data.put("birthday",info.getBirthday());}
        data.put("fans",follows.lambdaQuery().eq(Follow::getFollowUserId,id).count());
        data.put("followee",follows.lambdaQuery().eq(Follow::getUserId,id).count());
        return Result.ok(data);
    }

    @PutMapping("/user/profile") @Transactional
    public Result update(@RequestBody ProfileForm form){
        String name=trim(form.getNickName()),city=trim(form.getCity()),intro=trim(form.getIntroduce()),icon=trim(form.getIcon());
        if(name.isEmpty()||name.length()>32)return Result.fail("昵称须为1至32个字");
        if(city.length()>64||intro.length()>128)return Result.fail("城市或简介超出长度限制");
        if(form.getBirthday()!=null&&form.getBirthday().isAfter(LocalDate.now()))return Result.fail("生日不能晚于今天");
        if(!icon.isEmpty()&&!icon.matches("/imgs/(blogs/upload/[a-zA-Z0-9/_.-]+|icons/[a-zA-Z0-9_.-]+|blogs/[a-zA-Z0-9_.-]+)"))return Result.fail("请选择本地头像");
        Long uid=UserHolder.getUser().getId();
        users.lambdaUpdate().eq(User::getId,uid).set(User::getNickName,name).set(User::getIcon,icon).update();
        UserInfo info=infos.lambdaQuery().eq(UserInfo::getUserId,uid).one();
        if(info==null){info=new UserInfo().setId(ids.nextId()).setUserId(uid);infos.save(info);}
        infos.lambdaUpdate().eq(UserInfo::getUserId,uid).eq(UserInfo::getId,info.getId())
                .set(UserInfo::getCity,city).set(UserInfo::getIntroduce,intro)
                .set(UserInfo::getGender,form.getGender()).set(UserInfo::getBirthday,form.getBirthday()).update();
        return Result.ok();
    }

    @GetMapping("/user/connections/{id}")
    public Result connections(@PathVariable("id") Long id,@RequestParam("kind") String kind,@RequestParam(value="current",defaultValue="1") int current){
        if(!id.equals(UserHolder.getUser().getId()))return Result.fail("请查看自己的关注列表");
        if(current<1||!("fans".equals(kind)||"following".equals(kind)))return Result.fail("参数不正确");
        var query=follows.lambdaQuery();boolean fans="fans".equals(kind);
        if(fans)query.eq(Follow::getFollowUserId,id);else query.eq(Follow::getUserId,id);
        List<UserDTO> rows=new ArrayList<>();
        for(Follow f:query.orderByDesc(Follow::getId).page(new Page<>(current,10)).getRecords()){
            User u=users.getById(fans?f.getUserId():f.getFollowUserId());
            if(u!=null)rows.add(BeanUtil.copyProperties(u,UserDTO.class));
        }
        return Result.ok(rows);
    }

    @GetMapping("/voucher-order/mine")
    public Result mine(@RequestParam(value="current",defaultValue="1") int current){
        if(current<1)return Result.fail("页码不正确");
        List<Map<String,Object>> rows=new ArrayList<>();
        for(VoucherOrder order:orders.lambdaQuery().eq(VoucherOrder::getUserId,UserHolder.getUser().getId())
                .orderByDesc(VoucherOrder::getId).page(new Page<>(current,10)).getRecords()){
            Map<String,Object> row=new LinkedHashMap<>();row.put("id",order.getId());row.put("voucherId",order.getVoucherId());row.put("status",order.getStatus());row.put("createTime",order.getCreateTime());
            Voucher voucher=vouchers.getById(order.getVoucherId());
            if(voucher!=null){row.put("title",voucher.getTitle());row.put("payValue",voucher.getPayValue());row.put("shopId",voucher.getShopId());}
            rows.add(row);
        }
        return Result.ok(rows);
    }
    private String trim(String value){return value==null?"":value.trim();}
}
