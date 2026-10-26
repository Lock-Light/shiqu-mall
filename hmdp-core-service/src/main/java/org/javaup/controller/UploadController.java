package org.javaup.controller;
import org.javaup.dto.Result;
import org.javaup.utils.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;
@RestController @RequestMapping("/upload")
public class UploadController {
 @PostMapping("/blog") public Result upload(@RequestParam("file") MultipartFile file) throws IOException {
  String name=file.getOriginalFilename();
  if(name==null||!name.toLowerCase(Locale.ROOT).matches(".*\\.(png|jpe?g|webp)$"))return Result.fail("只支持JPG、PNG或WebP图片");
  if(file.isEmpty()||file.getSize()>5*1024*1024)return Result.fail("图片须为5MB以内的非空文件");
  String path="blogs/upload/"+UserHolder.getUser().getId()+"/"+UUID.randomUUID()+name.substring(name.lastIndexOf('.')).toLowerCase(Locale.ROOT);
  Path target=Paths.get(SystemConstants.IMAGE_UPLOAD_DIR).resolve(path);Files.createDirectories(target.getParent());file.transferTo(target);
  return Result.ok("/"+path);
 }
 @GetMapping("/blog/delete") public Result delete(@RequestParam("name") String name) throws IOException {
  String prefix="blogs/upload/"+UserHolder.getUser().getId()+"/";
  String relative=name.startsWith("/imgs/")?name.substring(6):name.replaceFirst("^/","");
  Path base=Paths.get(SystemConstants.IMAGE_UPLOAD_DIR).toAbsolutePath().normalize(),target=base.resolve(relative).normalize();
  if(!relative.startsWith(prefix)||!target.startsWith(base)||Files.isDirectory(target))return Result.fail("只能删除自己上传的图片");
  Files.deleteIfExists(target);return Result.ok();
 }
}
